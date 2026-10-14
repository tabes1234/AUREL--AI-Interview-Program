"""T5：表达客观指标（全部本地计算，不依赖任何外部服务）。

- WAV 解析：时长、采样率、单声道采样点
- 停顿检测：滑动窗口 RMS 静音判定 → 停顿次数 / 最长停顿 / 静音占比
- 语速：转录字数 / 语音时长（依赖真实转录，转录缺失时如实标注不可用）
- 填充词：转录文本模式计数
"""

import io
import re
import wave
import zipfile

from pydantic import BaseModel, Field


class AudioFormatError(Exception):
    """音频无法在本地解析（仅支持无压缩 WAV；其他格式交给 ASR 服务判断）。"""


WINDOW_MS = 30
PAUSE_THRESHOLD_RATIO = 0.08  # 窗口 RMS < 全局峰值 RMS 的 8% 视为静音


class PauseProfile(BaseModel):
    """本地静音检测得出的停顿画像。"""

    pause_count: int
    longest_pause_ms: int
    total_pause_ms: int
    silence_ratio: float  # 静音时长 / 音频总时长


class SpeechMetrics(BaseModel):
    """依赖转录文本的语速指标（转录不可用时 available=False）。"""

    available: bool
    unavailable_reason: str | None = None
    char_count: int = 0
    speech_rate_cpm: float | None = None  # 字 / 分钟（按语音净时长，扣除静音）
    filler_words: dict[str, int] = Field(default_factory=dict)
    filler_total: int = 0


FILLER_PATTERN = re.compile(r"嗯+|啊+|呃+|哎+|emm+|uh+|um+|那个|就是|然后|其实", re.IGNORECASE)


def parse_wav(audio: bytes) -> tuple[int, list[int], int]:
    """解析 WAV：返回 (duration_ms, 采样点列表, 采样率)。仅支持 PCM。"""
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            rate = wav.getframerate()
            frames = wav.getnframes()
            width = wav.getsampwidth()
            channels = wav.getnchannels()
            raw = wav.readframes(frames)
    except (wave.Error, EOFError, zipfile.BadZipFile) as exc:
        raise AudioFormatError("音频不是可解析的 WAV（PCM）格式") from exc
    if rate <= 0 or width not in (1, 2, 4):
        raise AudioFormatError("音频 WAV 参数异常（采样率或位深不支持）")

    duration_ms = int(frames * 1000 / rate)
    # 多声道取平均，按位宽解包为整数采样
    import struct

    if width == 2:
        count = len(raw) // 2
        samples = list(struct.unpack(f"<{count}h", raw[: count * 2]))
    elif width == 1:
        samples = [b - 128 for b in raw]
    else:
        count = len(raw) // 4
        samples = [v >> 16 for v in struct.unpack(f"<{count}i", raw[: count * 4])]
    if channels > 1:
        samples = samples[::channels]
    return duration_ms, samples, rate


def detect_pauses(samples: list[int], rate: int) -> PauseProfile:
    """滑动窗口 RMS 静音检测。窗口 30ms，阈值 = 峰值窗口 RMS 的 8%。"""
    total_ms = int(len(samples) * 1000 / rate) if rate else 0
    if total_ms == 0 or not samples:
        return PauseProfile(pause_count=0, longest_pause_ms=0, total_pause_ms=0, silence_ratio=0.0)

    window = max(1, int(rate * WINDOW_MS / 1000))
    window_rms: list[float] = []
    for start in range(0, len(samples), window):
        chunk = samples[start : start + window]
        if not chunk:
            break
        mean_sq = sum(s * s for s in chunk) / len(chunk)
        window_rms.append(mean_sq ** 0.5)

    peak = max(window_rms)
    if peak <= 0:
        return PauseProfile(pause_count=1, longest_pause_ms=total_ms, total_pause_ms=total_ms, silence_ratio=1.0)
    threshold = peak * PAUSE_THRESHOLD_RATIO

    silent_windows = [rms < threshold for rms in window_rms]
    pause_count = 0
    longest_pause_ms = 0
    current_run = 0
    total_silent_windows = 0
    for silent in silent_windows:
        if silent:
            current_run += 1
            total_silent_windows += 1
        else:
            if current_run > 0:
                pause_count += 1
                longest_pause_ms = max(longest_pause_ms, current_run * WINDOW_MS)
            current_run = 0
    if current_run > 0:
        pause_count += 1
        longest_pause_ms = max(longest_pause_ms, current_run * WINDOW_MS)
    # 忽略纯静音音频（峰值本身极低时上面的兜底已处理）；结尾静音计入停顿
    total_pause_ms = total_silent_windows * WINDOW_MS
    return PauseProfile(
        pause_count=pause_count,
        longest_pause_ms=longest_pause_ms,
        total_pause_ms=total_pause_ms,
        silence_ratio=round(total_pause_ms / total_ms, 4),
    )


def speech_metrics(transcript: str | None, duration_ms: int | None, pause: PauseProfile | None = None) -> SpeechMetrics:
    """语速与填充词。转录缺失时 available=False 并说明原因，不伪造。"""
    text = (transcript or "").strip()
    if not text:
        return SpeechMetrics(available=False, unavailable_reason="转录不可用，语速与填充词指标需要真实转录文本")

    chars = len(re.sub(r"\s", "", text))
    if not chars:
        return SpeechMetrics(available=False, unavailable_reason="转录文本为空")

    # 语速按「净说话时长」计算：扣除本地检测出的静音部分（有停顿画像时）
    net_ms = duration_ms
    if net_ms and net_ms > 0 and pause is not None:
        net_ms = max(1, net_ms - pause.total_pause_ms)
    rate = None
    if net_ms and net_ms > 0:
        rate = round(chars * 60000 / net_ms, 1)

    fillers: dict[str, int] = {}
    for match in FILLER_PATTERN.finditer(text):
        token = match.group(0).lower()
        fillers[token] = fillers.get(token, 0) + 1
    return SpeechMetrics(
        available=True,
        char_count=chars,
        speech_rate_cpm=rate,
        filler_words=dict(sorted(fillers.items(), key=lambda kv: -kv[1])),
        filler_total=sum(fillers.values()),
    )
