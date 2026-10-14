"""T5：可插拔语音识别（ASR）服务层。

三个提供方实现同一协议，按 ASR_PROVIDER（默认 auto）选择：
- siliconflow     硅基流动 · SenseVoiceSmall（OpenAI 兼容 /v1/audio/transcriptions，免费档）
- local_whisper   本地 faster-whisper（完全离线免费，首次自动经 HF 镜像下载模型）
- volcengine_flash 豆包语音 · 录音文件识别极速版（独立凭证，可选）

全部未就绪时工厂返回 None，调用方必须如实标注未配置状态，不得伪造转录。
"""

import importlib.util
import io
import logging
import os
import re
import tempfile
import threading
import wave
import zipfile
from dataclasses import dataclass, field

import httpx

from app.config import (
    asr_configured,
    asr_hf_endpoint,
    asr_provider_preference,
    local_whisper_model,
    siliconflow_api_key,
    speech_access_token,
    speech_api_url,
    speech_app_id,
)

logger = logging.getLogger("aurel.asr")

REQUEST_TIMEOUT_SECONDS = 120.0

SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
SILICONFLOW_ASR_MODEL = "FunAudioLLM/SenseVoiceSmall"

SENSEVOICE_TAG = re.compile(r"<\|[^|]{1,24}\|>")


class AsrError(Exception):
    """ASR 调用失败（网络、HTTP 错误或响应异常），message 面向用户可读。"""


class AsrNotConfiguredError(AsrError):
    """提供方凭证或依赖未就绪。"""


@dataclass
class Utterance:
    """句级分段（含时间戳，用于停顿分析）。"""

    text: str
    start_time_ms: int
    end_time_ms: int


@dataclass
class TranscriptionResult:
    text: str
    provider: str
    duration_ms: int | None = None
    utterances: list[Utterance] = field(default_factory=list)


class AsrProvider:
    """ASR 提供方协议：实现 transcribe 即可接入新的语音服务。"""

    name: str = "base"
    label: str = "base"

    def transcribe(self, audio: bytes, filename: str, content_type: str | None = None) -> TranscriptionResult:
        raise NotImplementedError


def _brief_body(text: str, limit: int = 200) -> str:
    compact = " ".join(text.split())
    return compact[:limit] + ("…" if len(compact) > limit else "")


class SiliconFlowAsr(AsrProvider):
    """硅基流动语音转文本（OpenAI 兼容接口，SenseVoiceSmall 免费档）。

    文档：https://docs.siliconflow.cn/docs/api/audio-transcriptions-post
    请求：multipart（file + model）；响应：{"text": "..."}。
    SenseVoice 输出可能带 <|zh|><|NEUTRAL|> 之类的语言/情绪标记，按已知格式清理，不改动识别内容。
    """

    name = "siliconflow"
    label = "硅基流动 · SenseVoice（免费档）"

    def transcribe(self, audio: bytes, filename: str, content_type: str | None = None) -> TranscriptionResult:
        api_key = siliconflow_api_key()
        if not api_key:
            raise AsrNotConfiguredError(
                "语音识别尚未配置：缺少环境变量 ASR_SILICONFLOW_API_KEY。"
                "请在硅基流动（siliconflow.cn）注册并创建 API Key，"
                "配置到 backend/.env 后重启后端服务。"
            )

        files = {"file": (filename or "audio.wav", audio, content_type or "audio/wav")}
        data = {"model": SILICONFLOW_ASR_MODEL}
        try:
            response = httpx.post(
                SILICONFLOW_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files=files,
                data=data,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise AsrError(f"语音识别请求超时（{REQUEST_TIMEOUT_SECONDS:.0f} 秒），请稍后重试") from exc
        except httpx.HTTPError as exc:
            raise AsrError(f"无法连接语音识别服务：{exc.__class__.__name__}") from exc

        if response.status_code in (401, 403):
            raise AsrError(
                f"语音识别认证失败（HTTP {response.status_code}）：请检查 ASR_SILICONFLOW_API_KEY 是否正确"
            )
        if response.status_code == 429:
            raise AsrError("语音识别调用达到限额（HTTP 429）：免费额度有限，请稍后重试")
        if response.status_code != 200:
            raise AsrError(
                f"语音识别服务返回错误（HTTP {response.status_code}）：{_brief_body(response.text)}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AsrError("语音识别服务返回了无法解析的响应") from exc

        raw_text = str(payload.get("text") or "")
        text = SENSEVOICE_TAG.sub("", raw_text).strip()
        if not text:
            raise AsrError("语音识别完成但未识别到有效语音内容")
        return TranscriptionResult(text=text, provider=self.name)


def _wav_to_float32_16k(audio: bytes):
    """WAV(PCM) → 16kHz float32 单声道 numpy 数组；不可解析时返回 None。

    本地解码绕开 faster-whisper 内部的 PyAV 依赖（新版 PyAV 移除了
    metadata_errors 参数且无 cp313 旧版 wheel），前端上传的音频均为 WAV。
    """
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            rate = wav.getframerate()
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            raw = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError, zipfile.BadZipFile):
        return None
    if rate <= 0 or not raw or width not in (1, 2, 4):
        return None

    import numpy as np

    if width == 2:
        usable = len(raw) - len(raw) % 2
        data = np.frombuffer(raw[:usable], dtype="<i2").astype(np.float32) / 32768.0
    elif width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        usable = len(raw) - len(raw) % 4
        data = np.frombuffer(raw[:usable], dtype="<i4").astype(np.float32) / 2147483648.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    if data.size == 0:
        return None

    if rate != 16000:
        target_len = int(round(data.size * 16000 / rate))
        if target_len <= 0:
            return None
        x_old = np.linspace(0.0, 1.0, num=data.size, endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=target_len, endpoint=False)
        data = np.interp(x_new, x_old, data).astype(np.float32)
    return data


class LocalWhisperAsr(AsrProvider):
    """本地 faster-whisper：完全离线、免费、不需要任何凭证。

    首次使用自动下载模型（经 HF_ENDPOINT，默认 hf-mirror.com 国内镜像），
    之后常驻内存；模型按 ASR_LOCAL_MODEL 配置（默认 small，中文可用性较好）。
    """

    name = "local_whisper"
    label = "本地 Whisper（离线免费）"

    _model_lock = threading.Lock()
    _model_cache: dict[str, object] = {}

    def transcribe(self, audio: bytes, filename: str, content_type: str | None = None) -> TranscriptionResult:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise AsrNotConfiguredError(
                "本地语音识别不可用：未安装 faster-whisper。"
                "请在后端 Python 环境执行 pip install faster-whisper 后重启服务。"
            ) from exc

        # huggingface_hub 在导入时读取 HF_ENDPOINT，须在首次导入前设好默认镜像
        os.environ.setdefault("HF_ENDPOINT", asr_hf_endpoint())
        size = local_whisper_model()
        model = self._get_model(WhisperModel, size)

        # WAV 优先本地解码（绕开 PyAV）；其余格式写临时文件交给 faster-whisper
        wav_audio = _wav_to_float32_16k(audio)
        tmp_path = ""
        try:
            if wav_audio is not None:
                segments, info = model.transcribe(wav_audio, vad_filter=True)
            else:
                suffix = os.path.splitext(filename or "audio.bin")[1] or ".bin"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(audio)
                    tmp_path = tmp.name
                segments, info = model.transcribe(tmp_path, vad_filter=True)
            text = "".join(segment.text for segment in segments).strip()
            duration_ms = int(info.duration * 1000) if info and getattr(info, "duration", None) else None
        except AsrError:
            raise
        except Exception as exc:  # ctranslate2 运行时错误种类较多，统一转可读失败
            raise AsrError(f"本地语音识别失败：{exc.__class__.__name__}: {str(exc)[:160]}") from exc
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        if not text:
            raise AsrError("语音识别完成但未识别到有效语音内容")
        return TranscriptionResult(text=text, provider=f"{self.name}:{size}", duration_ms=duration_ms)

    @classmethod
    def _get_model(cls, whisper_model_cls, size: str):
        key = f"cpu:int8:{size}"
        with cls._model_lock:
            if key not in cls._model_cache:
                logger.info("loading local whisper model %s (first use downloads via mirror)", size)
                cls._model_cache[key] = whisper_model_cls(size, device="cpu", compute_type="int8")
            return cls._model_cache[key]


class VolcengineFlashAsr(AsrProvider):
    """豆包语音 · 大模型录音文件识别（极速版，同步 HTTP，二进制音频直传）。

    官方文档：https://www.volcengine.com/docs/6561/1631584
    认证：X-Api-App-Key + X-Api-Access-Token（语音控制台创建应用后获取）。
    响应含 result.text 与 result.utterances（句级 start_time / end_time，毫秒）。
    """

    name = "volcengine_flash"
    label = "豆包语音 · 录音文件识别（极速版）"

    def transcribe(self, audio: bytes, filename: str, content_type: str | None = None) -> TranscriptionResult:
        app_id = speech_app_id()
        access_token = speech_access_token()
        if not app_id or not access_token:
            raise AsrNotConfiguredError(
                "语音识别尚未配置：缺少环境变量 SPEECH_APP_ID、SPEECH_ACCESS_TOKEN。"
                "请在豆包语音控制台创建应用后，在 backend/.env 中配置并重启后端服务。"
            )

        headers = {
            "X-Api-App-Key": app_id,
            "X-Api-Access-Key": access_token,
            "Content-Type": content_type or "audio/wav",
        }
        try:
            response = httpx.post(
                speech_api_url(),
                params={"appid": app_id, "language": "zh-CN"},
                headers=headers,
                content=audio,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise AsrError(f"语音识别请求超时（{REQUEST_TIMEOUT_SECONDS:.0f} 秒），请稍后重试") from exc
        except httpx.HTTPError as exc:
            raise AsrError(f"无法连接语音识别服务：{exc.__class__.__name__}") from exc

        if response.status_code == 401 or response.status_code == 403:
            raise AsrError(
                f"语音识别认证失败（HTTP {response.status_code}）："
                "请检查 SPEECH_APP_ID 与 SPEECH_ACCESS_TOKEN 是否正确、服务是否已开通"
            )
        if response.status_code == 429:
            raise AsrError("语音识别调用达到限额（HTTP 429）：额度不足或请求过于频繁")
        if response.status_code != 200:
            raise AsrError(
                f"语音识别服务返回错误（HTTP {response.status_code}）：{_brief_body(response.text)}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise AsrError("语音识别服务返回了无法解析的响应") from exc

        meta = data.get("meta") or {}
        code = meta.get("status_code")
        if code not in (0, None, 20000000, 20000001, 20000002, 20000003):
            message = meta.get("message") or "未知错误"
            raise AsrError(f"语音识别失败（错误码 {code}）：{message}")

        result = data.get("result") or {}
        text = str(result.get("text") or "").strip()
        utterances = _parse_utterances(result.get("utterances") or [])
        if not text and not utterances:
            raise AsrError("语音识别完成但未识别到有效语音内容")
        text = text or " ".join(u.text for u in utterances).strip()
        return TranscriptionResult(
            text=text,
            provider=self.name,
            duration_ms=_infer_duration_ms(result, utterances),
            utterances=utterances,
        )


def _parse_utterances(raw: list) -> list[Utterance]:
    parsed: list[Utterance] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        parsed.append(
            Utterance(
                text=text,
                start_time_ms=int(item.get("start_time") or 0),
                end_time_ms=int(item.get("end_time") or 0),
            )
        )
    return parsed


def _infer_duration_ms(result: dict, utterances: list[Utterance]) -> int | None:
    audio_info = result.get("audio_info") or {}
    for key in ("duration", "duration_ms"):
        value = audio_info.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return int(value if key.endswith("_ms") else value * 1000)
    if utterances:
        return max(u.end_time_ms for u in utterances)
    return None


# ---- 提供方注册与选择 ----

_AUTO_ORDER = ("siliconflow", "volcengine_flash", "local_whisper")

_PREFERENCE_ALIASES = {
    "siliconflow": "siliconflow",
    "silicon_flow": "siliconflow",
    "local": "local_whisper",
    "local_whisper": "local_whisper",
    "whisper": "local_whisper",
    "volcengine": "volcengine_flash",
    "volcengine_flash": "volcengine_flash",
    "doubao": "volcengine_flash",
}


def local_whisper_installed() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def _local_model_cached(size: str) -> bool:
    hf_home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    return os.path.isdir(os.path.join(hf_home, "hub", f"models--Systran--faster-whisper-{size}"))


def _provider_ready(kind: str) -> bool:
    if kind == "siliconflow":
        return bool(siliconflow_api_key())
    if kind == "local_whisper":
        return local_whisper_installed() and _local_model_cached(local_whisper_model())
    if kind == "volcengine_flash":
        return asr_configured()
    return False


def _build_provider(kind: str) -> AsrProvider:
    if kind == "siliconflow":
        return SiliconFlowAsr()
    if kind == "local_whisper":
        return LocalWhisperAsr()
    return VolcengineFlashAsr()


def get_asr_provider() -> AsrProvider | None:
    """工厂：按 ASR_PROVIDER 选择就绪的提供方；全部未就绪返回 None（调用方须如实标注）。"""
    preference = _PREFERENCE_ALIASES.get(asr_provider_preference(), "")
    if preference:
        return _build_provider(preference) if _provider_ready(preference) else None
    for kind in _AUTO_ORDER:
        if _provider_ready(kind):
            return _build_provider(kind)
    return None


def _provider_status(kind: str) -> dict:
    if kind == "siliconflow":
        missing = [] if siliconflow_api_key() else ["ASR_SILICONFLOW_API_KEY"]
        return {
            "label": SiliconFlowAsr.label,
            "configured": not missing,
            "missing_env": missing,
            "setup": "在 backend/.env 配置 ASR_SILICONFLOW_API_KEY（siliconflow.cn 免费注册）",
        }
    if kind == "local_whisper":
        size = local_whisper_model()
        installed = local_whisper_installed()
        return {
            "label": LocalWhisperAsr.label,
            "configured": installed and _local_model_cached(size),
            "installed": installed,
            "model": size,
            "model_cached": _local_model_cached(size),
            "missing_env": [] if installed else [],
            "setup": "" if installed else "在后端 Python 环境执行 pip install faster-whisper",
        }
    missing = []
    if not speech_app_id():
        missing.append("SPEECH_APP_ID")
    if not speech_access_token():
        missing.append("SPEECH_ACCESS_TOKEN")
    return {
        "label": VolcengineFlashAsr.label,
        "configured": not missing,
        "missing_env": missing,
        "setup": "在 backend/.env 配置 SPEECH_APP_ID 与 SPEECH_ACCESS_TOKEN（豆包语音控制台）",
    }


def asr_status() -> dict:
    """配置状态（不泄露密钥），供前端展示与测试断言。"""
    providers = {kind: _provider_status(kind) for kind in _AUTO_ORDER}
    active = get_asr_provider()
    active_info = providers[active.name] if active is not None else None

    missing_env: list[str] = []
    if active is None:
        seen: set[str] = set()
        for info in providers.values():
            for env in info["missing_env"]:
                if env and env not in seen:
                    seen.add(env)
                    missing_env.append(env)

    return {
        "configured": active is not None,
        "provider": active.name if active is not None else None,
        "provider_label": active_info["label"] if active_info is not None else None,
        "missing_env": missing_env,
        "preference": asr_provider_preference(),
        "providers": providers,
    }
