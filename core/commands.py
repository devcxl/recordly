"""撤销/重做命令系统 — 纯数据层，无 Qt 依赖"""

from dataclasses import dataclass
from abc import ABC, abstractmethod


class UndoCommand(ABC):
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
    clip_index: int
    old_start: float
    new_start: float
    old_end: float
    new_end: float
    old_track: int = -1
    new_track: int = -1

    def execute(self, timeline):
        if self.new_track >= 0 and self.new_track != self.old_track:
            clip = timeline._tracks[self.old_track].clips.pop(self.clip_index)
            timeline._tracks[self.new_track].clips.append(clip)
            clip.start = self.new_start
            clip.end = self.new_end
        else:
            t = timeline._tracks[self.track_index]
            clip = t.clips[self.clip_index]
            clip.start = self.new_start
            clip.end = self.new_end

    def undo(self, timeline):
        if self.new_track >= 0 and self.new_track != self.old_track:
            clip = timeline._tracks[self.new_track].clips.pop()
            timeline._tracks[self.old_track].clips.insert(self.clip_index, clip)
            clip.start = self.old_start
            clip.end = self.old_end
        else:
            t = timeline._tracks[self.track_index]
            clip = t.clips[self.clip_index]
            clip.start = self.old_start
            clip.end = self.old_end

    def __repr__(self):
        return f"MoveClip(t{self.track_index}: {self.old_start:.1f}→{self.new_start:.1f})"


@dataclass
class DeleteClipCommand(UndoCommand):
    track_index: int
    clip_index: int
    clip_data: dict | None = None

    def execute(self, timeline):
        t = timeline._tracks[self.track_index]
        if not self.clip_data:
            from dataclasses import asdict
            self.clip_data = asdict(t.clips[self.clip_index])
        del t.clips[self.clip_index]

    def undo(self, timeline):
        if self.clip_data:
            from core.project import Clip
            t = timeline._tracks[self.track_index]
            t.clips.insert(self.clip_index, Clip(**self.clip_data))


@dataclass
class SplitClipCommand(UndoCommand):
    track_index: int
    clip_index: int
    split_time: float
    right_clip_data: dict | None = None
    old_end: float = 0.0

    def execute(self, timeline):
        t = timeline._tracks[self.track_index]
        clip = t.clips[self.clip_index]
        self.old_end = clip.end
        clip.end = self.split_time
        self.right_clip_data = {
            "type": clip.type, "start": self.split_time, "end": self.old_end,
            "speed": clip.speed, "content": clip.content,
        }
        from core.project import Clip
        t.clips.insert(self.clip_index + 1, Clip(**self.right_clip_data))

    def undo(self, timeline):
        del timeline._tracks[self.track_index].clips[self.clip_index + 1]
        timeline._tracks[self.track_index].clips[self.clip_index].end = self.old_end
