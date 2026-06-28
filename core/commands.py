"""撤销/重做命令系统 — 纯数据层，无 Qt 依赖"""

from dataclasses import dataclass
from abc import ABC, abstractmethod


class UndoCommand(ABC):
    """可撤销操作的基类"""

    @abstractmethod
    def execute(self, timeline):
        ...

    @abstractmethod
    def undo(self, timeline):
        ...

    def __repr__(self):
        return self.__class__.__name__


@dataclass
class MoveClipCommand(UndoCommand):
    track_index: int
    old_start: float
    new_start: float
    old_end: float
    new_end: float

    def execute(self, timeline):
        timeline._tracks[self.track_index].start = self.new_start
        timeline._tracks[self.track_index].end = self.new_end

    def undo(self, timeline):
        timeline._tracks[self.track_index].start = self.old_start
        timeline._tracks[self.track_index].end = self.old_end

    def __repr__(self):
        return f"MoveClip(t{self.track_index}: {self.old_start:.1f}→{self.new_start:.1f})"


@dataclass
class DeleteClipCommand(UndoCommand):
    track_index: int
    track_data: dict | None = None

    def execute(self, timeline):
        if not self.track_data:
            from dataclasses import asdict
            self.track_data = asdict(timeline._tracks[self.track_index])
        del timeline._tracks[self.track_index]

    def undo(self, timeline):
        if self.track_data:
            from core.project import Track
            timeline._tracks.insert(self.track_index, Track(**self.track_data))


@dataclass
class SplitClipCommand(UndoCommand):
    track_index: int
    split_time: float
    new_track_data: dict | None = None
    old_end: float = 0.0

    def execute(self, timeline):
        t = timeline._tracks[self.track_index]
        self.old_end = t.end
        t.end = self.split_time
        self.new_track_data = {
            "type": t.type, "start": self.split_time, "end": self.old_end,
            "speed": t.speed, "content": t.content,
        }
        from core.project import Track
        timeline._tracks.insert(self.track_index + 1, Track(**self.new_track_data))

    def undo(self, timeline):
        del timeline._tracks[self.track_index + 1]
        timeline._tracks[self.track_index].end = self.old_end
