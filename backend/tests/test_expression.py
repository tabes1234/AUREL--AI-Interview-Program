"""T5 表达客观指标 / T6 多角色工作流测试。

覆盖：WAV 解析与停顿检测、语速与填充词、ASR 未配置状态（不伪造转录）、
mock provider 真实转录路径、多角色工作流结构化输出与失败处理。
"""

import io
import struct
import wave
from pathlib import Path

import httpx
import pytest

from app.config import asr_configured
from app.services import audio_metrics
from app.services.asr_service import (
    AsrError,
    SiliconFlowAsr,
    TranscriptionResult,
    Utterance,
    VolcengineFlashAsr,
    asr_status,
    get_asr_provider,
)
from app.services.expression_workflow import run_expression_workflow

from .conftest import use_fake_client


# ---------- helpers ----------

def clear_asr_cache() -> None:
    asr_configured.cache_clear()


def disable_local_asr(monkeypatch) -> None:
    """未配置场景的确定性：硅基流动无 key、本地 Whisper 视为不可用。"""
    import app.services.asr_service as asr_service

    monkeypatch.setenv("ASR_SILICONFLOW_API_KEY", "")
    monkeypatch.setattr(asr_service, "local_whisper_installed", lambda: False)
    monkeypatch.setattr(asr_service, "_local_model_cached", lambda size: False)


def make_wav(seconds: float, rate: int = 8000, segments: list[tuple[float, float]] | None = None) -> bytes:
    """生成测试 WAV。segments 指定有声区间（秒）；其余区间静音。"""
    total = int(seconds * rate)
    speaking = set()
    if segments is None:
        speaking = set(range(total))
    else:
        for start, end in segments:
            for i in range(int(start * rate), min(int(end * rate), total)):
                speaking.add(i)
    frames = bytearray()
    for i in range(total):
        amp = 3000 if i in speaking else 0
        frames += struct.pack("<h", amp)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))
    return buf.getvalue()


def coach_output() -> dict:
    return {
        "overall_assessment": "回答结构完整，但缺少具体数据支撑。",
        "priority_fixes": [
            {"title": "补充量化结果", "detail": "为项目经历添加性能数字与业务收益"},
        ],
        "drill_suggestions": ["练习 STAR 法则复述项目", "每分钟语速控制在 180 字左右"],
    }


def structure_output() -> dict:
    return {
        "logic_score": 6.5,
        "structure_summary": "总分总结构，衔接自然。",
        "discourse_markers": ["首先", "其次"],
        "issues": [{"type": "逻辑跳跃", "evidence": "直接跳到结论", "suggestion": "补充推理过程"}],
    }


def depth_output() -> dict:
    return {
        "depth_score": 5.0,
        "concrete_examples": ["压测 QPS 提升 40%"],
        "missing_substance": ["缺少失败案例的复盘"],
        "issues": [{"type": "论据缺失", "evidence": "没有说明技术选型原因", "suggestion": "补充权衡分析"}],
    }


# ---------- T5 本地客观指标 ----------

class TestWavParsing:
    def test_duration_and_rate(self):
        wav = make_wav(2.0)
        duration_ms, samples, rate = audio_metrics.parse_wav(wav)
        assert duration_ms == 2000
        assert rate == 8000
        assert len(samples) == 16000

    def test_invalid_format_rejected(self):
        with pytest.raises(audio_metrics.AudioFormatError):
            audio_metrics.parse_wav(b"not a wav file at all")

    def test_webm_magic_rejected(self):
        with pytest.raises(audio_metrics.AudioFormatError):
            audio_metrics.parse_wav(b"\x1aE\xdf\xa3webm-header-bytes")


class TestPauseDetection:
    def test_silence_between_segments(self):
        # 1 秒有声 → 0.8 秒静音 → 1 秒有声 = 2.8 秒，中间一处停顿
        wav = make_wav(2.8, rate=8000, segments=[(0.0, 1.0), (1.8, 2.8)])
        duration_ms, samples, rate = audio_metrics.parse_wav(wav)
        profile = audio_metrics.detect_pauses(samples, rate)
        assert profile.pause_count >= 1
        assert profile.longest_pause_ms >= 600
        assert 0.15 <= profile.silence_ratio <= 0.45
        assert duration_ms == 2800

    def test_continuous_speech_no_pause(self):
        wav = make_wav(1.0)
        _, samples, rate = audio_metrics.parse_wav(wav)
        profile = audio_metrics.detect_pauses(samples, rate)
        assert profile.pause_count == 0
        assert profile.silence_ratio == 0.0

    def test_all_silent(self):
        wav = make_wav(1.0, segments=[])
        _, samples, rate = audio_metrics.parse_wav(wav)
        profile = audio_metrics.detect_pauses(samples, rate)
        assert profile.silence_ratio == 1.0


class TestSpeechMetrics:
    def test_rate_and_fillers(self):
        transcript = "嗯，我觉得这个项目就是，首先做了压测，然后性能提升了，那个效果还不错。"
        metrics = audio_metrics.speech_metrics(transcript, 10_000)
        assert metrics.available is True
        assert metrics.char_count > 0
        assert metrics.speech_rate_cpm is not None and metrics.speech_rate_cpm > 0
        assert metrics.filler_total >= 3
        assert metrics.filler_words.get("嗯", 0) >= 1

    def test_no_transcript_is_honest(self):
        metrics = audio_metrics.speech_metrics(None, 10_000)
        assert metrics.available is False
        assert metrics.unavailable_reason
        assert metrics.speech_rate_cpm is None

    def test_net_speaking_time_excludes_silence(self):
        # 10 秒音频，其中 4 秒静音：语速应按 6 秒净时长计算（更快）
        transcript = "回答完整内容" * 10
        with_silence = audio_metrics.speech_metrics(
            transcript, 10_000,
            audio_metrics.PauseProfile(pause_count=1, longest_pause_ms=4000, total_pause_ms=4000, silence_ratio=0.4),
        )
        without_silence = audio_metrics.speech_metrics(transcript, 10_000)
        assert with_silence.speech_rate_cpm is not None
        assert without_silence.speech_rate_cpm is not None
        assert with_silence.speech_rate_cpm > without_silence.speech_rate_cpm


# ---------- T5 ASR 可插拔层 ----------

class TestAsrStatus:
    def test_not_configured_by_default(self, monkeypatch):
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        disable_local_asr(monkeypatch)
        clear_asr_cache()
        try:
            status = asr_status()
            assert status["configured"] is False
            assert set(status["missing_env"]) == {
                "ASR_SILICONFLOW_API_KEY",
                "SPEECH_APP_ID",
                "SPEECH_ACCESS_TOKEN",
            }
            assert get_asr_provider() is None
        finally:
            clear_asr_cache()

    def test_configured_returns_provider(self, monkeypatch):
        monkeypatch.setenv("SPEECH_APP_ID", "test-app")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "test-token")
        disable_local_asr(monkeypatch)
        clear_asr_cache()
        try:
            provider = get_asr_provider()
            assert provider is not None
            assert provider.name == "volcengine_flash"
        finally:
            clear_asr_cache()


class FakeAsrProvider:
    name = "fake_asr"

    def __init__(self, result: TranscriptionResult | None = None, error: AsrError | None = None):
        self.result = result
        self.error = error
        self.calls: list[tuple[bytes, str]] = []

    def transcribe(self, audio: bytes, filename: str, content_type: str | None = None) -> TranscriptionResult:
        self.calls.append((audio, filename))
        if self.error:
            raise self.error
        return self.result


class TestVolcengineFlashAsr:
    def test_raises_when_not_configured(self, monkeypatch):
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        provider = VolcengineFlashAsr()
        with pytest.raises(AsrError, match="语音识别尚未配置"):
            provider.transcribe(b"audio-bytes", "a.wav")

    def test_http_401_maps_to_auth_error(self, monkeypatch):
        monkeypatch.setenv("SPEECH_APP_ID", "app")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "token")
        monkeypatch.setenv("SPEECH_API_URL", "http://asr.test/flash")

        def fake_post(url, **kwargs):
            return httpx.Response(401, json={"error": "bad key"}, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        provider = VolcengineFlashAsr()
        with pytest.raises(AsrError, match="认证失败"):
            provider.transcribe(b"audio", "a.wav")

    def test_business_error_code_maps_to_error(self, monkeypatch):
        monkeypatch.setenv("SPEECH_APP_ID", "app")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "token")
        monkeypatch.setenv("SPEECH_API_URL", "http://asr.test/flash")

        def fake_post(url, **kwargs):
            body = {"meta": {"status_code": 45000001, "message": "quota exhausted"}, "result": None}
            return httpx.Response(200, json=body, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        provider = VolcengineFlashAsr()
        with pytest.raises(AsrError, match="45000001"):
            provider.transcribe(b"audio", "a.wav")

    def test_success_parses_utterances(self, monkeypatch):
        monkeypatch.setenv("SPEECH_APP_ID", "app")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "token")
        monkeypatch.setenv("SPEECH_API_URL", "http://asr.test/flash")

        def fake_post(url, **kwargs):
            body = {
                "meta": {"status_code": 0, "message": "Success"},
                "result": {
                    "text": "你好世界",
                    "audio_info": {"duration": 2.5},
                    "utterances": [
                        {"text": "你好", "start_time": 0, "end_time": 1200},
                        {"text": "世界", "start_time": 1500, "end_time": 2500},
                    ],
                },
            }
            return httpx.Response(200, json=body, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        provider = VolcengineFlashAsr()
        result = provider.transcribe(b"audio", "a.wav")
        assert result.text == "你好世界"
        assert result.duration_ms == 2500
        assert len(result.utterances) == 2
        assert result.utterances[1].end_time_ms == 2500


class TestSiliconFlowAsr:
    def test_requires_api_key(self, monkeypatch):
        monkeypatch.setenv("ASR_SILICONFLOW_API_KEY", "")
        with pytest.raises(AsrError, match="ASR_SILICONFLOW_API_KEY"):
            SiliconFlowAsr().transcribe(b"audio", "a.wav")

    def test_success_cleans_sensevoice_tags(self, monkeypatch):
        monkeypatch.setenv("ASR_SILICONFLOW_API_KEY", "sk-test")
        captured: dict = {}

        def fake_post(url, **kwargs):
            captured["url"] = url
            captured["auth"] = kwargs["headers"]["Authorization"]
            captured["data"] = kwargs["data"]
            body = {"text": "<|zh|><|NEUTRAL|>大家好，我讲一下项目经验。"}
            return httpx.Response(200, json=body, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        result = SiliconFlowAsr().transcribe(b"audio", "a.wav")
        assert result.text == "大家好，我讲一下项目经验。"
        assert result.provider == "siliconflow"
        assert captured["url"] == "https://api.siliconflow.cn/v1/audio/transcriptions"
        assert captured["auth"] == "Bearer sk-test"
        assert captured["data"]["model"] == "FunAudioLLM/SenseVoiceSmall"

    def test_auth_failure_maps_to_readable_error(self, monkeypatch):
        monkeypatch.setenv("ASR_SILICONFLOW_API_KEY", "sk-bad")

        def fake_post(url, **kwargs):
            return httpx.Response(401, json={"message": "invalid key"}, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        with pytest.raises(AsrError, match="认证失败"):
            SiliconFlowAsr().transcribe(b"audio", "a.wav")

    def test_empty_text_raises(self, monkeypatch):
        monkeypatch.setenv("ASR_SILICONFLOW_API_KEY", "sk-test")

        def fake_post(url, **kwargs):
            return httpx.Response(200, json={"text": "<|zh|>"}, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        with pytest.raises(AsrError, match="未识别到有效语音"):
            SiliconFlowAsr().transcribe(b"audio", "a.wav")

    def test_server_error_maps_to_readable_error(self, monkeypatch):
        monkeypatch.setenv("ASR_SILICONFLOW_API_KEY", "sk-test")

        def fake_post(url, **kwargs):
            return httpx.Response(500, text="boom", request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx, "post", fake_post)
        with pytest.raises(AsrError, match="HTTP 500"):
            SiliconFlowAsr().transcribe(b"audio", "a.wav")


class TestProviderSelection:
    def test_auto_returns_none_when_all_disabled(self, monkeypatch):
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        disable_local_asr(monkeypatch)
        clear_asr_cache()
        try:
            assert get_asr_provider() is None
        finally:
            clear_asr_cache()

    def test_auto_prefers_siliconflow_over_volcengine(self, monkeypatch):
        disable_local_asr(monkeypatch)
        monkeypatch.setenv("ASR_SILICONFLOW_API_KEY", "sk")
        monkeypatch.setenv("SPEECH_APP_ID", "app")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "tok")
        clear_asr_cache()
        try:
            provider = get_asr_provider()
            assert provider is not None and provider.name == "siliconflow"
        finally:
            clear_asr_cache()

    def test_auto_falls_back_to_volcengine(self, monkeypatch):
        disable_local_asr(monkeypatch)
        monkeypatch.setenv("SPEECH_APP_ID", "app")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "tok")
        clear_asr_cache()
        try:
            provider = get_asr_provider()
            assert provider is not None and provider.name == "volcengine_flash"
        finally:
            clear_asr_cache()

    def test_auto_selects_cached_local_whisper(self, monkeypatch):
        import app.services.asr_service as asr_service

        monkeypatch.setenv("ASR_SILICONFLOW_API_KEY", "")
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        clear_asr_cache()
        monkeypatch.setattr(asr_service, "local_whisper_installed", lambda: True)
        monkeypatch.setattr(asr_service, "_local_model_cached", lambda size: True)
        try:
            provider = get_asr_provider()
            assert provider is not None and provider.name == "local_whisper"
        finally:
            clear_asr_cache()

    def test_local_installed_but_model_missing_is_not_ready(self, monkeypatch):
        import app.services.asr_service as asr_service

        monkeypatch.setenv("ASR_SILICONFLOW_API_KEY", "")
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        clear_asr_cache()
        monkeypatch.setattr(asr_service, "local_whisper_installed", lambda: True)
        monkeypatch.setattr(asr_service, "_local_model_cached", lambda size: False)
        try:
            assert get_asr_provider() is None
        finally:
            clear_asr_cache()

    def test_explicit_preference_not_ready_returns_none(self, monkeypatch):
        monkeypatch.setenv("ASR_PROVIDER", "volcengine")
        monkeypatch.setenv("ASR_SILICONFLOW_API_KEY", "sk")
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        clear_asr_cache()
        try:
            assert get_asr_provider() is None
        finally:
            clear_asr_cache()


class TestLocalWhisperReal:
    """真实集成：模型已缓存且示例语音存在时，验证本地转录链路（其余环境自动跳过）。"""

    def test_real_transcription_when_model_cached(self, monkeypatch):
        pytest.importorskip("faster_whisper")
        import app.services.asr_service as asr_service

        sample = Path(__file__).parent / "assets" / "sample_speech.wav"
        if not sample.exists():
            pytest.skip("缺少示例语音文件 tests/assets/sample_speech.wav")
        monkeypatch.setenv("ASR_PROVIDER", "local")
        provider = asr_service.get_asr_provider()
        assert provider is not None and provider.name == "local_whisper"
        result = provider.transcribe(sample.read_bytes(), "sample_speech.wav")
        assert result.text and len(result.text) >= 2
        assert result.duration_ms is not None and result.duration_ms > 0


# ---------- T5 API 集成 ----------

class TestTranscribeApi:
    def test_status_endpoint(self, api_client, monkeypatch):
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        disable_local_asr(monkeypatch)
        clear_asr_cache()
        try:
            response = api_client.get("/api/v1/expression/status")
            assert response.status_code == 200
            data = response.json()
            assert data["asr"]["configured"] is False
            assert "SPEECH_APP_ID" in data["asr"]["missing_env"]
            assert "ASR_SILICONFLOW_API_KEY" in data["asr"]["missing_env"]
            assert data["asr"]["providers"]["siliconflow"]["configured"] is False
            assert data["asr"]["providers"]["volcengine_flash"]["configured"] is False
            assert data["asr"]["preference"] == "auto"
            assert data["ark"]["configured"] is True
            assert data["audio_limits"]["max_mb"] == 20
        finally:
            clear_asr_cache()

    def test_upload_wav_without_asr_no_fake_transcript(self, api_client, monkeypatch):
        """核心约定：ASR 未配置时，转录必须为空且如实标注，本地指标照常返回。"""
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        disable_local_asr(monkeypatch)
        clear_asr_cache()
        try:
            wav = make_wav(1.0)
            response = api_client.post(
                "/api/v1/expression/transcribe",
                files={"file": ("test.wav", wav, "audio/wav")},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["transcript"] is None
            assert data["asr_status"] == "not_configured"
            assert "未生成转录" in data["asr_error"]
            assert "ASR_SILICONFLOW_API_KEY" in data["asr_error"]
            assert data["audio"]["available"] is True
            assert data["audio"]["duration_ms"] == 1000
            assert data["speech"]["available"] is False
            assert data["speech"]["unavailable_reason"]
        finally:
            clear_asr_cache()

    def test_upload_with_mock_asr_full_result(self, api_client, monkeypatch):
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        clear_asr_cache()

        fake = FakeAsrProvider(
            result=TranscriptionResult(
                text="嗯，我觉得首先做了压测，然后性能提升了。",
                provider="fake_asr",
                utterances=[Utterance("嗯，我觉得首先做了压测。", 0, 2000)],
            )
        )
        import app.routers.expression as expression_router
        monkeypatch.setattr(expression_router, "get_asr_provider", lambda: fake)

        try:
            wav = make_wav(2.0)
            response = api_client.post(
                "/api/v1/expression/transcribe",
                files={"file": ("test.wav", wav, "audio/wav")},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["asr_status"] == "ok"
            assert data["asr_provider"] == "fake_asr"
            assert data["transcript"] == "嗯，我觉得首先做了压测，然后性能提升了。"
            assert data["audio"]["available"] is True
            assert data["speech"]["available"] is True
            assert data["speech"]["filler_total"] >= 2
            listing = api_client.get("/api/v1/expression/records").json()
            assert any(r["id"] == data["id"] and r["has_transcript"] for r in listing)
        finally:
            clear_asr_cache()

    def test_upload_asr_failure_recorded_honestly(self, api_client, monkeypatch):
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        clear_asr_cache()

        fake = FakeAsrProvider(error=AsrError("语音识别服务返回错误（HTTP 500）"))
        import app.routers.expression as expression_router
        monkeypatch.setattr(expression_router, "get_asr_provider", lambda: fake)

        try:
            wav = make_wav(1.0)
            response = api_client.post(
                "/api/v1/expression/transcribe",
                files={"file": ("test.wav", wav, "audio/wav")},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["asr_status"] == "failed"
            assert data["transcript"] is None
            assert "HTTP 500" in data["asr_error"]
        finally:
            clear_asr_cache()

    def test_unsupported_format_415(self, api_client):
        response = api_client.post(
            "/api/v1/expression/transcribe",
            files={"file": ("song.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 415

    def test_empty_file_400(self, api_client):
        response = api_client.post(
            "/api/v1/expression/transcribe",
            files={"file": ("empty.wav", b"", "audio/wav")},
        )
        assert response.status_code == 400


# ---------- T6 多角色工作流 ----------

class TestExpressionWorkflow:
    def _steps(self):
        from app.services.expression_workflow import default_steps
        return default_steps()

    def test_all_steps_complete(self):
        fake = use_fake_client([structure_output(), depth_output(), coach_output()])
        result = run_expression_workflow("一段完整的回答文本" * 5, steps=self._steps(), client=fake)
        assert result["status"] == "completed"
        roles = [s["role"] for s in result["steps"]]
        assert roles == ["structure_analyst", "depth_analyst", "expression_coach"]
        assert all(s["status"] == "completed" for s in result["steps"])
        assert result["steps"][0]["output"]["logic_score"] == 6.5
        coach_system, coach_user = fake.calls[2]
        assert "结构分析师报告" in coach_user

    def test_structured_validation_failure_retries(self):
        # 第一次输出缺字段 → 重试；后续正确 → 成功
        fake = use_fake_client(
            [{"wrong": "shape"}, structure_output(), depth_output(), coach_output()]
        )
        result = run_expression_workflow("一段完整的回答文本" * 5, steps=self._steps(), client=fake)
        assert result["status"] == "completed"
        assert result["steps"][0]["attempts"] == 2
        assert result["steps"][0]["error"] is None

    def test_step_failure_marks_dependents_skipped(self):
        # 前两步始终失败，依赖它们的第三步应被 skipped，整体 failed
        fake = use_fake_client([{"nonsense": True}] * 6)
        result = run_expression_workflow("一段完整的回答文本" * 5, steps=self._steps(), client=fake)
        statuses = {s["role"]: s["status"] for s in result["steps"]}
        assert statuses["structure_analyst"] == "failed"
        assert statuses["depth_analyst"] == "failed"
        assert statuses["expression_coach"] == "skipped"
        assert result["status"] == "failed"
        skipped = next(s for s in result["steps"] if s["role"] == "expression_coach")
        assert "依赖的步骤未完成" in skipped["error"]

    def test_partial_when_one_step_fails(self):
        fake = use_fake_client(
            [structure_output(), {"bad": 1}, {"bad": 2}, {"bad": 3}, {"bad": 4}]
        )
        result = run_expression_workflow("一段完整的回答文本" * 5, steps=self._steps(), client=fake)
        statuses = {s["role"]: s["status"] for s in result["steps"]}
        assert statuses["structure_analyst"] == "completed"
        assert statuses["depth_analyst"] == "failed"
        assert statuses["expression_coach"] == "skipped"
        assert result["status"] == "partial"

    def test_coach_output_schema_coercion(self):
        coerced = {
            "overall_assessment": "整体尚可。",
            "priority_fixes": ["先补量化数据"],
            "drill_suggestions": ["每日复述练习"],
        }
        fake = use_fake_client([structure_output(), depth_output(), coerced])
        result = run_expression_workflow("一段完整的回答文本" * 5, steps=self._steps(), client=fake)
        assert result["status"] == "completed"
        coach = result["steps"][2]["output"]
        assert coach["priority_fixes"][0]["title"] == "先补量化数据"


class TestAnalyzeApi:
    def test_analyze_with_text(self, api_client):
        use_fake_client([structure_output(), depth_output(), coach_output()])
        response = api_client.post(
            "/api/v1/expression/analyze",
            json={"text": "这是一段足够长的面试回答内容，用来测试多角色工作流的分析流程是否可以正常运转。" * 2},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["workflow"]["status"] == "completed"
        assert len(data["workflow"]["steps"]) == 3
        assert data["asr_status"] == "not_attempted"

    def test_analyze_requires_text_or_id(self, api_client):
        response = api_client.post("/api/v1/expression/analyze", json={})
        assert response.status_code == 400

    def test_analyze_referencing_record_without_transcript_conflicts(self, api_client, monkeypatch):
        # ASR 未配置 → 上传记录无转录 → 引用分析应 409
        monkeypatch.setenv("SPEECH_APP_ID", "")
        monkeypatch.setenv("SPEECH_ACCESS_TOKEN", "")
        disable_local_asr(monkeypatch)
        clear_asr_cache()
        try:
            wav = make_wav(1.0)
            upload = api_client.post(
                "/api/v1/expression/transcribe",
                files={"file": ("a.wav", wav, "audio/wav")},
            ).json()
            assert upload["asr_status"] == "not_configured"
            response = api_client.post(
                "/api/v1/expression/analyze", json={"analysis_id": upload["id"]}
            )
            assert response.status_code == 409
        finally:
            clear_asr_cache()

    def test_analyze_referencing_transcript_with_text(self, api_client, monkeypatch):
        clear_asr_cache()
        fake_asr = FakeAsrProvider(
            result=TranscriptionResult(text="我主导了一次数据库迁移，把查询耗时从两秒降到两百毫秒。" * 2, provider="fake_asr")
        )
        import app.routers.expression as expression_router
        monkeypatch.setattr(expression_router, "get_asr_provider", lambda: fake_asr)
        wav = make_wav(1.0)
        upload = api_client.post(
            "/api/v1/expression/transcribe",
            files={"file": ("a.wav", wav, "audio/wav")},
        ).json()
        assert upload["asr_status"] == "ok"

        use_fake_client([structure_output(), depth_output(), coach_output()])
        response = api_client.post(
            "/api/v1/expression/analyze", json={"analysis_id": upload["id"]}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["transcript"] == upload["transcript"]
        assert data["workflow"]["status"] == "completed"

    def test_records_detail_and_delete(self, api_client):
        use_fake_client([structure_output(), depth_output(), coach_output()])
        created = api_client.post(
            "/api/v1/expression/analyze",
            json={"text": "这是一段足够长的面试回答内容，用来测试记录的查询与删除。" * 2},
        ).json()
        detail = api_client.get(f"/api/v1/expression/records/{created['id']}")
        assert detail.status_code == 200
        assert detail.json()["workflow"]["status"] == "completed"
        deleted = api_client.delete(f"/api/v1/expression/records/{created['id']}")
        assert deleted.status_code == 204
        assert api_client.get(f"/api/v1/expression/records/{created['id']}").status_code == 404

    def test_404_for_missing_record(self, api_client):
        assert api_client.get("/api/v1/expression/records/9999").status_code == 404
