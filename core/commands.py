"""撤销/重做命令系统 — 纯数据层，无 Qt 依赖"""

from dataclasses import dataclass
from abc import ABC, abstractmethod
from uuid import uuid4
from core.speed import plan_clip_speed_change


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
    old_source_start: float = 0.0
    new_source_start: float = 0.0
    old_source_end: float | None = None
    new_source_end: float | None = None

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
        clip.source_start = self.new_source_start
        clip.source_end = self.new_source_end

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
        clip.source_start = self.old_source_start
        clip.source_end = self.old_source_end

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
    old_source_end: float | None = None

    def execute(self, timeline):
        t = timeline._tracks[self.track_index]
        clip = t.clips[self.clip_index]
        self.old_end = clip.end
        self.old_source_end = clip.source_end
        source_end = (
            clip.source_end
            if clip.source_end is not None
            else clip.source_start + (clip.end - clip.start) * clip.speed
        )
        split_source = clip.source_start + (
            self.split_time - clip.start) * clip.speed

        from dataclasses import asdict
        self.right_clip_data = asdict(clip)
        self.right_clip_data.update({
            "id": str(uuid4()),
            "start": self.split_time,
            "end": self.old_end,
            "source_start": split_source,
            "source_end": source_end,
        })
        clip.end = self.split_time
        clip.source_end = split_source
        from core.project import Clip
        t.clips.insert(self.clip_index + 1, Clip(**self.right_clip_data))

    def undo(self, timeline):
        del timeline._tracks[self.track_index].clips[self.clip_index + 1]
        clip = timeline._tracks[self.track_index].clips[self.clip_index]
        clip.end = self.old_end
        clip.source_end = self.old_source_end


@dataclass
class ChangeSpeedCommand(UndoCommand):
    track_index: int
    clip_index: int
    old_speed: float
    new_speed: float
    old_end: float

    def execute(self, timeline):
        clip = timeline._tracks[self.track_index].clips[self.clip_index]
        clip.speed = self.new_speed
        if clip.source_end is not None:
            source_duration = clip.source_end - clip.source_start
            clip.end = max(
                clip.start + 0.1,
                clip.start + source_duration / self.new_speed,
            )
        else:
            result = plan_clip_speed_change(
                clip.start, self.old_end, self.old_speed, self.new_speed)
            if "new_end" in result:
                clip.end = max(clip.start + 0.1, result["new_end"])

    def undo(self, timeline):
        clip = timeline._tracks[self.track_index].clips[self.clip_index]
        clip.speed = self.old_speed
        clip.end = self.old_end


@dataclass
class CompositeCommand(UndoCommand):
    """将多个子命令组合为单个可撤销/重做单元。
    execute: 顺序执行子命令
    undo:    逆序撤销子命令
    """
    sub_commands: list  # list[UndoCommand]

    def execute(self, timeline):
        for cmd in self.sub_commands:
            cmd.execute(timeline)

    def undo(self, timeline):
        for cmd in reversed(self.sub_commands):
            cmd.undo(timeline)

    def __repr__(self):
        inner = ', '.join(repr(c) for c in self.sub_commands)
        return f"Composite({inner})"
