"""预览播放控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ui.audio_preview_player import AudioPreviewPlayer

if TYPE_CHECKING:
    from ui.preview_widget import PreviewWidget


class PlaybackController:
    """预览播放控制器，管理播放状态与帧索引"""

    def __init__(self, widget: PreviewWidget, compositor,
                 audio_result=None, video_clips=None, audio_player=None):
        self.widget = widget
        self.compositor = compositor
        self._playing = False
        self._paused = False
        self._current_frame = 0
        self._total_frames = self._get_total_frames()
        self._step = 1
        self._on_frame_changed = None
        self._audio_player = audio_player
        if self._audio_player is None and audio_result is not None:
            # 向后兼容分支：无注入 player 时创建空播放器（新签名 regions 为空），
            # 避免旧 AudioPreviewPlayer(audio_result, video_clips) 签名调用崩溃
            self._audio_player = AudioPreviewPlayer([], 44100)
        self._audio_clock = False

    def _get_total_frames(self) -> int:
        return int(getattr(
            self.compositor, "total_output_frames",
            len(self.compositor.frames),
        ))

    @property
    def total_frames(self) -> int:
        return self._total_frames

    @property
    def current_frame(self) -> int:
        return self._current_frame

    def set_on_frame_changed(self, callback):
        self._on_frame_changed = callback

    def play(self, start: int = 0):
        self._total_frames = self._get_total_frames()
        if self._total_frames == 0:
            return
        if start >= self._total_frames - 1:
            start = 0
        self._current_frame = start
        self._playing = True
        self._paused = False
        self._step = 1
        self._audio_clock = bool(
            self._audio_player
            and self._audio_player.start(start / self.compositor.fps)
        )
        self._start_generator()

    def _start_generator(self):
        def gen():
            idx = self._current_frame
            while idx < self._total_frames:
                if self._paused:
                    return
                if not self._playing:
                    return
                if self._audio_clock:
                    idx = min(
                        int(self._audio_player.current_time * self.compositor.fps),
                        self._total_frames - 1,
                    )
                frame = self.compositor.compose_index(idx)
                self._current_frame = idx
                if self._on_frame_changed:
                    self._on_frame_changed(idx)
                yield frame
                if self._audio_clock and self._audio_player.finished:
                    self._playing = False
                    self._audio_player.close()
                    self._audio_clock = False
                    return
                if not self._audio_clock:
                    idx += self._step
            self._playing = False
        self.widget.start_playback(gen())

    def pause(self):
        if not self._playing:
            return
        self._paused = not self._paused
        if self._paused:
            self.widget.stop_playback()
            if self._audio_player:
                self._audio_player.pause()
        else:
            if self._audio_player:
                self._audio_clock = self._audio_player.resume()
            self._start_generator()

    @property
    def is_paused(self) -> bool:
        return self._paused

    def stop(self):
        self._playing = False
        self._paused = False
        self._current_frame = 0
        self._step = 1
        self._audio_clock = False
        if self._audio_player:
            self._audio_player.close()
            self._audio_player.seek(0)
        self.widget.stop_playback()
        frame = self.compositor.compose_index(0)
        if frame:
            self.widget.show_frame(frame)
        if self._on_frame_changed:
            self._on_frame_changed(0)

    def seek(self, index: int):
        self._total_frames = self._get_total_frames()
        if self._total_frames == 0:
            self._current_frame = 0
            return
        index = max(0, min(index, self._total_frames - 1))
        self._current_frame = index
        if self._audio_player:
            self._audio_player.seek(index / self.compositor.fps)
        frame = self.compositor.compose_index(index)
        if frame:
            self.widget.show_frame(frame)
        if self._on_frame_changed:
            self._on_frame_changed(index)

    def step_forward(self):
        self.seek(self._current_frame + 1)

    def step_backward(self):
        self.seek(self._current_frame - 1)

    def fast_forward(self):
        self._step = min(self._step * 2, 16)
        if self._audio_clock and self._audio_player:
            self._audio_player.close()
            self._audio_clock = False
        if not self._paused and self._playing:
            self.widget.stop_playback()
            self._start_generator()

    def rewind(self):
        self._step = 1
        self.seek(self._current_frame - 10)

    def reset_speed(self):
        self._step = 1
