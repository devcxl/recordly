"""时间线音频预览播放器。"""

import numpy as np
import sounddevice as sd

from core.audio_mix import compose_audio


class AudioPreviewPlayer:
    """将编辑后的时间线音频送入声卡，并暴露已消费样本的时间。"""

    def __init__(self, audio_regions, samplerate, duration=None,
                 stream_factory=None):
        self.samplerate = int(samplerate)
        self._stream_factory = stream_factory or sd.OutputStream
        composed = compose_audio(audio_regions, samplerate, duration)
        self._timeline_data = (
            composed if composed is not None
            else np.zeros((0, 1), dtype=np.float32)
        )
        self._cursor = 0
        self._stream = None
        self._active = False

    @property
    def timeline_data(self) -> np.ndarray:
        return self._timeline_data

    @property
    def current_time(self) -> float:
        return self._cursor / self.samplerate

    @property
    def duration(self) -> float:
        return len(self._timeline_data) / self.samplerate

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def finished(self) -> bool:
        return self._cursor >= len(self._timeline_data)

    def _audio_callback(self, outdata, frames, _time_info, _status):
        end = min(self._cursor + frames, len(self._timeline_data))
        count = max(0, end - self._cursor)
        outdata.fill(0)
        if count:
            outdata[:count] = self._timeline_data[self._cursor:end]
        self._cursor = end

    def start(self, seconds: float | None = None) -> bool:
        if seconds is not None:
            self.seek(seconds)
        self.close()
        if not len(self._timeline_data):
            return False
        try:
            self._stream = self._stream_factory(
                samplerate=self.samplerate,
                channels=self._timeline_data.shape[1],
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            self._active = True
            return True
        except Exception:
            self.close()
            return False

    def pause(self):
        if self._stream is not None:
            self._stream.stop()
        self._active = False

    def resume(self) -> bool:
        return self.start()

    def seek(self, seconds: float):
        self._cursor = max(0, min(
            round(seconds * self.samplerate), len(self._timeline_data)
        ))

    def close(self):
        stream = self._stream
        self._stream = None
        self._active = False
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

