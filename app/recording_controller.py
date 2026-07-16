"""录制控制器 — 统一录制入口、状态机与失败恢复"""

from enum import Enum
from typing import Callable

from core.recorder import Recorder


class RecordingState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    RECORDING = "recording"
    STOPPING = "stopping"


class RecordingStartError(RuntimeError):
    pass


class RecordingStopError(RuntimeError):
    def __init__(self, message: str, recoverable: bool = False):
        super().__init__(message)
        self.recoverable = recoverable


class RecordingController:
    """录制控制器。纯 Python，可独立测试。"""

    def __init__(self, config):
        self._recorder = Recorder(target_fps=config.default_fps)
        self._state = RecordingState.IDLE
        self._on_state_changed: Callable[[RecordingState], None] | None = None
        self._on_error: Callable[[str, bool], None] | None = None

    @property
    def state(self) -> RecordingState:
        return self._state

    @property
    def recorder(self) -> Recorder:
        return self._recorder

    def start(self, project_dir: str) -> None:
        if self._state != RecordingState.IDLE:
            raise RuntimeError(f"无法在状态 {self._state.value} 启动录制")
        self._set_state(RecordingState.STARTING)
        try:
            self._recorder.start_recording(project_dir)
        except Exception as exc:
            self._set_state(RecordingState.IDLE)
            raise RecordingStartError(str(exc)) from exc
        self._set_state(RecordingState.RECORDING)

    def stop(self) -> dict:
        if self._state != RecordingState.RECORDING:
            raise RuntimeError(f"无法在状态 {self._state.value} 停止录制")
        self._set_state(RecordingState.STOPPING)
        try:
            result = self._recorder.stop_recording()
        except Exception as exc:
            self._set_state(RecordingState.IDLE)
            raise RecordingStopError(str(exc), recoverable=True) from exc
        self._set_state(RecordingState.IDLE)
        return result

    def set_callbacks(self,
                       on_state_changed: Callable[[RecordingState], None] | None = None,
                       on_error: Callable[[str, bool], None] | None = None):
        self._on_state_changed = on_state_changed
        self._on_error = on_error

    def cleanup(self):
        self._set_state(RecordingState.IDLE)

    def _set_state(self, state: RecordingState):
        self._state = state
        if self._on_state_changed:
            self._on_state_changed(state)
