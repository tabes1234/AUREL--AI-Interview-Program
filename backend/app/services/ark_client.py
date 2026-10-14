"""火山方舟 Chat Completions 客户端（模型适配层）。

所有第三方模型调用只能通过本模块在服务端执行，
API Key 从环境变量读取，绝不进入前端或日志。

T8 稳定性：连接/读取超时分离；对网络错误与 429/5xx 自动重试（尊重 Retry-After）；
T10 观测：每次调用（成功或失败）写入 llm_call_records，支持实验模型按比例分流。
"""

import atexit
import contextlib
import json
import logging
import random
import threading
import time
from collections.abc import Iterator
from contextlib import AbstractContextManager

import httpx

from app.config import ark_api_key, ark_base_url, ark_model, llm_experiment_model, llm_experiment_percent
from app.services.prompt_registry import version_for

logger = logging.getLogger("aurel.ark")

REQUEST_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
MAX_RETRIES = 2  # 首次请求之外的最大重试次数
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
# JSON 结构化输出的生成上限：远高于实际任务所需（评分/解析类通常 < 2500 tokens），
# 防止模型偶发长尾输出拖长等待；仅设上限，正常输出在 EOS 处自然停止，不受影响。
JSON_MAX_TOKENS = 6000

# 性能优化：模块级共享连接池。避免每次模型调用重新建立 TCP/TLS 连接
# （每次握手约几十至几百毫秒，在串行多段调用如「出题→评分」中累积明显）。
# httpx.Client 官方保证线程安全，可被 FastAPI 线程池中的同步路由共享。
_SHARED_CLIENT_LOCK = threading.Lock()
_SHARED_CLIENT: httpx.Client | None = None


def _close_shared_client() -> None:
    global _SHARED_CLIENT
    if _SHARED_CLIENT is not None:
        _SHARED_CLIENT.close()
        _SHARED_CLIENT = None


def _shared_http_client() -> httpx.Client:
    global _SHARED_CLIENT
    if _SHARED_CLIENT is None or _SHARED_CLIENT.is_closed:
        with _SHARED_CLIENT_LOCK:
            if _SHARED_CLIENT is None or _SHARED_CLIENT.is_closed:
                _SHARED_CLIENT = httpx.Client(
                    timeout=REQUEST_TIMEOUT,
                    limits=httpx.Limits(
                        max_connections=32,
                        max_keepalive_connections=8,
                        # 用户两次 AI 操作常间隔数分钟，30s 保活会让连接频繁失效重建；
                        # 延长到 5 分钟可显著提升复用率（服务端提前断开时 httpx 会自动重连，安全）
                        keepalive_expiry=300.0,
                    ),
                )
                atexit.register(_close_shared_client)
    return _SHARED_CLIENT


def warmup_connection() -> None:
    """后台预热共享连接池：提前完成与模型服务的 TCP/TLS 握手，
    消除服务重启后首次 AI 调用的建连延迟。失败静默，不影响服务启动。
    未配置 ARK_API_KEY 时不预热。"""
    if not ark_api_key():
        return

    def _warm() -> None:
        try:
            base = ark_base_url().rstrip("/")
            _shared_http_client().get(base, timeout=httpx.Timeout(10.0, connect=5.0))
            logger.info("ark connection warmup ok: %s", base)
        except Exception:  # noqa: BLE001 — 预热失败静默，真实调用仍会按需建连
            logger.info("ark connection warmup skipped (service unreachable)")

    threading.Thread(target=_warm, name="ark-warmup", daemon=True).start()


def _post(url: str, *, headers: dict, json: dict, timeout: httpx.Timeout) -> httpx.Response:
    """统一模型 POST 入口（共享连接池；模块级函数便于测试替换）。"""
    return _shared_http_client().post(url, headers=headers, json=json, timeout=timeout)


class ArkError(Exception):
    """方舟调用失败（网络、HTTP 错误或响应异常），message 面向用户可读。"""


class ArkNotConfiguredError(ArkError):
    """未配置 ARK_API_KEY 或 ARK_MODEL。"""


class ArkClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None,
                 transport: httpx.BaseTransport | None = None) -> None:
        self._api_key = api_key if api_key is not None else ark_api_key()
        self._base_url = (base_url or ark_base_url()).rstrip("/")
        self._model = model if model is not None else ark_model()
        self._transport = transport  # 仅供测试注入 MockTransport

    @property
    def model(self) -> str:
        return self._model

    def ensure_configured(self) -> None:
        if not self._api_key or not self._model:
            missing = []
            if not self._api_key:
                missing.append("ARK_API_KEY")
            if not self._model:
                missing.append("ARK_MODEL")
            raise ArkNotConfiguredError(
                f"AI 模型尚未配置：缺少环境变量 {'、'.join(missing)}。"
                "请在 backend/.env 中配置后重启后端服务。"
            )

    def _resolve_model(self) -> tuple[str, bool]:
        """T10 实验分流：按 LLM_EXPERIMENT_PERCENT 概率路由到实验模型。"""
        experiment_model = llm_experiment_model()
        percent = llm_experiment_percent()
        if experiment_model and percent > 0 and random.random() * 100 < percent:
            return experiment_model, True
        return self._model, False

    def chat(self, system: str, user: str, *, temperature: float = 0.7,
             service: str = "unattributed", max_tokens: int | None = None) -> str:
        """单轮对话调用，返回模型文本输出。失败自动重试并记录观测。"""
        self.ensure_configured()
        used_model, is_experiment = self._resolve_model()
        payload = {
            "model": used_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        started = time.monotonic()
        attempts = 0
        usage: dict | None = None
        content: str | None = None
        error_type: str | None = None
        error_message: str | None = None

        try:
            while attempts < MAX_RETRIES + 1:
                attempts += 1
                retry_delay = 0.0
                try:
                    response = _post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=REQUEST_TIMEOUT,
                    )
                except httpx.TimeoutException as exc:
                    error_type, error_message = exc.__class__.__name__, (
                        f"AI 模型请求超时（{REQUEST_TIMEOUT.read:.0f} 秒），请稍后重试"
                    )
                    retry_delay = 0.5 * (2 ** (attempts - 1))
                except httpx.HTTPError as exc:
                    error_type, error_message = exc.__class__.__name__, (
                        f"无法连接 AI 模型服务：{exc.__class__.__name__}"
                    )
                    retry_delay = 0.5 * (2 ** (attempts - 1))
                else:
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            content = data["choices"][0]["message"]["content"]
                            raw_usage = data.get("usage")
                            if isinstance(raw_usage, dict):
                                usage = raw_usage
                        except (ValueError, KeyError, IndexError) as exc:
                            error_type, error_message = "BadResponse", (
                                "AI 模型返回了无法解析的响应结构"
                            )
                        else:
                            if isinstance(content, str) and content.strip():
                                break  # 成功
                            content = None
                            error_type, error_message = "BadResponse", "AI 模型返回了空内容"
                        retry_delay = 0.5 * (2 ** (attempts - 1))
                    elif response.status_code in RETRYABLE_STATUS and attempts <= MAX_RETRIES:
                        error_type = f"HTTP{response.status_code}"
                        error_message = _status_message(response.status_code, response.text)
                        retry_after = response.headers.get("retry-after")
                        try:
                            retry_delay = min(5.0, max(0.0, float(retry_after)))
                        except (TypeError, ValueError):
                            retry_delay = 0.5 * (2 ** (attempts - 1))
                    else:
                        # 不可重试的 HTTP 错误，直接失败
                        error_type = f"HTTP{response.status_code}"
                        error_message = _status_message(response.status_code, response.text)
                        break

                if retry_delay and attempts <= MAX_RETRIES:
                    logger.info(
                        "ark call retrying: service=%s attempt=%d delay=%.1fs error=%s",
                        service, attempts, retry_delay, error_message,
                    )
                    time.sleep(retry_delay)
        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            from app.services.llm_observability import record_llm_call

            record_llm_call(
                service=service,
                model=used_model,
                prompt_version=version_for(service),
                status="success" if content is not None else "error",
                attempts=attempts,
                latency_ms=latency_ms,
                error_type=None if content is not None else (error_type or "UnknownError"),
                error_message=error_message,
                experiment=is_experiment,
                usage=usage,
            )

        if content is None:
            raise ArkError(error_message or "AI 模型调用失败")
        return content

    def chat_json(self, system: str, user: str, *, temperature: float = 0.3,
                  service: str = "unattributed") -> dict:
        """要求 JSON 输出并健壮解析（容忍 markdown 代码块包裹）。

        结构化输出统一设生成上限（JSON_MAX_TOKENS），防止偶发长尾输出拖长等待。
        """
        raw = self.chat(
            system + "\n请只输出 JSON，不要包含其他文字或代码块标记。",
            user,
            temperature=temperature,
            service=service,
            max_tokens=JSON_MAX_TOKENS,
        )
        return parse_json_output(raw)

    def chat_stream(self, system: str, user: str, *, temperature: float = 0.7,
                    service: str = "unattributed") -> Iterator[str]:
        """流式对话调用：逐段 yield 模型文本增量（OpenAI 兼容 SSE）。

        连接阶段对网络错误与 429/5xx 自动重试；一旦开始输出就不再重试，
        中途失败抛出 ArkError，由调用方决定如何保留已生成内容。
        """
        self.ensure_configured()
        used_model, is_experiment = self._resolve_model()
        payload = {
            "model": used_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        started = time.monotonic()
        attempts = 0
        usage: dict | None = None
        error_type: str | None = None
        error_message: str | None = None
        produced = False
        succeeded = False

        try:
            while attempts < MAX_RETRIES + 1:
                attempts += 1
                retry_delay = 0.0
                try:
                    client_cm: AbstractContextManager[httpx.Client]
                    if self._transport is not None:
                        # 测试注入 MockTransport：使用独立客户端
                        client_cm = httpx.Client(timeout=REQUEST_TIMEOUT, transport=self._transport)
                    else:
                        # 共享连接池：nullcontext 退出时不关闭共享客户端
                        client_cm = contextlib.nullcontext(_shared_http_client())
                    with client_cm as http:
                        with http.stream(
                            "POST",
                            f"{self._base_url}/chat/completions",
                            headers=headers,
                            json=payload,
                        ) as response:
                            if response.status_code != 200:
                                body = response.read()
                                error_type = f"HTTP{response.status_code}"
                                error_message = _status_message(response.status_code, body.decode("utf-8", "replace"))
                                if response.status_code in RETRYABLE_STATUS and attempts <= MAX_RETRIES and not produced:
                                    retry_after = response.headers.get("retry-after")
                                    try:
                                        retry_delay = min(5.0, max(0.0, float(retry_after)))
                                    except (TypeError, ValueError):
                                        retry_delay = 0.5 * (2 ** (attempts - 1))
                                else:
                                    break
                            else:
                                succeeded = True
                                for line in response.iter_lines():
                                    delta = _parse_sse_delta(line)
                                    if delta is None:
                                        continue
                                    produced = True
                                    yield delta
                                if not produced:
                                    succeeded = False
                                    error_type, error_message = "BadResponse", "AI 模型返回了空内容"
                                break
                except httpx.HTTPError as exc:
                    if produced:
                        # 已开始输出：中断不可重试，如实抛错（调用方可保留已生成内容）
                        error_type, error_message = exc.__class__.__name__, (
                            "AI 模型流式响应中断，已生成的内容会尽量保留，请稍后重试"
                        )
                        succeeded = False
                        break
                    if isinstance(exc, httpx.TimeoutException):
                        error_type, error_message = exc.__class__.__name__, (
                            f"AI 模型请求超时（{REQUEST_TIMEOUT.read:.0f} 秒），请稍后重试"
                        )
                    else:
                        error_type, error_message = exc.__class__.__name__, (
                            f"无法连接 AI 模型服务：{exc.__class__.__name__}"
                        )
                    retry_delay = 0.5 * (2 ** (attempts - 1))

                if retry_delay and attempts <= MAX_RETRIES:
                    logger.info(
                        "ark stream retrying: service=%s attempt=%d delay=%.1fs error=%s",
                        service, attempts, retry_delay, error_message,
                    )
                    time.sleep(retry_delay)
        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            from app.services.llm_observability import record_llm_call

            record_llm_call(
                service=service,
                model=used_model,
                prompt_version=version_for(service),
                status="success" if succeeded and produced else "error",
                attempts=attempts,
                latency_ms=latency_ms,
                error_type=None if succeeded and produced else (error_type or "UnknownError"),
                error_message=error_message,
                experiment=is_experiment,
                usage=usage,
            )

        if not succeeded or not produced:
            raise ArkError(error_message or "AI 模型调用失败")


def _parse_sse_delta(line: str) -> str | None:
    """解析 OpenAI 兼容 SSE 行，返回文本增量；非数据行或空增量返回 None。"""
    stripped = line.strip()
    if not stripped.startswith("data:"):
        return None
    data = stripped[5:].strip()
    if not data or data == "[DONE]":
        return None
    try:
        chunk = json.loads(data)
    except json.JSONDecodeError:
        return None
    if not isinstance(chunk, dict):
        return None
    raw_usage = chunk.get("usage")
    if isinstance(raw_usage, dict):
        return None  # usage 块不是文本增量
    choices = chunk.get("choices")
    delta = (choices[0].get("delta") or {}) if choices else {}
    content = delta.get("content")
    return content if isinstance(content, str) and content else None


def _status_message(status_code: int, body: str) -> str:
    if status_code == 401:
        return "AI 模型认证失败（HTTP 401）：请检查 ARK_API_KEY 是否正确或已过期"
    if status_code == 429:
        return "AI 模型调用达到限额（HTTP 429）：额度不足或请求过于频繁"
    return f"AI 模型服务返回错误（HTTP {status_code}）：{_brief_body(body)}"


def parse_json_output(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        # 剥离 ```json ... ``` 包裹
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # 兜底：提取首个大括号到末个大括号之间的内容
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ArkError(f"AI 模型输出不是有效的 JSON：{_brief_body(raw)}")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ArkError(f"AI 模型输出不是有效的 JSON：{_brief_body(raw)}") from exc
    if not isinstance(parsed, dict):
        raise ArkError("AI 模型输出的 JSON 结构不符合预期（应为对象）")
    return parsed


def _brief_body(text: str, limit: int = 200) -> str:
    compact = " ".join(text.split())
    return compact[:limit] + ("…" if len(compact) > limit else "")
