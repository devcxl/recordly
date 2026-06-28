"""时间线组件 — 轨道可视化和交互编辑"""

from PyQt5.QtWidgets import QWidget, QMenu
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush

from dataclasses import dataclass, field
from abc import ABC, abstractmethod


# ── 撤销/重做命令系统 ──────────────────────────────────────

class UndoCommand(ABC):
    """可撤销操作的基类"""

    @abstractmethod
    def execute(self, timeline: "TimelineWidget"):
        ...

    @abstractmethod
    def undo(self, timeline: "TimelineWidget"):
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
    _executed: bool = False

    def execute(self, timeline):
        timeline._tracks[self.track_index].start = self.new_start
        timeline._tracks[self.track_index].end = self.new_end
        self._executed = True

    def undo(self, timeline):
        timeline._tracks[self.track_index].start = self.old_start
        timeline._tracks[self.track_index].end = self.old_end
        timeline._tracks[self.track_index + 1].start = self.old_start if hasattr(self, '_split_end') else None

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


# ── 时间线控件 ────────────────────────────────────────────

TRACK_COLORS = {
    "video": QColor("#4A90D9"),
    "audio": QColor("#50C878"),
    "cursor": QColor("#E8A838"),
    "text": QColor("#A855F7"),
    "zoom": QColor("#F97316"),
}
TIMELINE_HEIGHT = 120
TRACK_HEIGHT = 24
RULER_HEIGHT = 20
PADDING = 20


class TimelineWidget(QWidget):
    """QPainter 时间线控件，支持拖拽编辑 + 撤销/重做"""

    SnapDistance = 5  # 吸附像素距离

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks = []                 # list[Track]
        self._playhead_s = 0.0
        self._duration = 60.0
        self._pixels_per_sec = 30.0
        self._selected = -1               # 选中的轨道索引
        self._drag_state = None           # None / "move" / "resize_left" / "resize_right"
        self._drag_index = -1
        self._drag_start_x = 0
        self._drag_orig_start = 0.0
        self._drag_orig_end = 0.0

        # 撤销栈
        self._undo_stack: list[UndoCommand] = []
        self._redo_stack: list[UndoCommand] = []

        self.setFixedHeight(TIMELINE_HEIGHT + RULER_HEIGHT + 10)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ── 属性 ──────────────────────────────────────────────

    @property
    def duration(self) -> float:
        return self._duration

    @duration.setter
    def duration(self, v: float):
        self._duration = max(v, 5.0)
        self.update()

    @property
    def playhead(self) -> float:
        return self._playhead_s

    @playhead.setter
    def playhead(self, s: float):
        self._playhead_s = max(0.0, min(s, self._duration))
        self.update()

    @property
    def tracks(self) -> list:
        return self._tracks

    def set_tracks(self, tracks: list):
        self._tracks = tracks
        self._selected = -1
        self.update()

    @property
    def active_tracks(self) -> list[dict]:
        """导出用的活动轨道列表（时间线可见范围）"""
        return [
            t for t in self._tracks
            if t.start <= self._playhead_s < t.end
        ]

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    # ── 撤销/重做 ─────────────────────────────────────────

    def _push_undo(self, cmd: UndoCommand):
        self._undo_stack.append(cmd)
        self._redo_stack.clear()
        cmd.execute(self)
        self.update()

    def undo(self):
        if not self._undo_stack:
            return
        cmd = self._undo_stack.pop()
        cmd.undo(self)
        self._redo_stack.append(cmd)
        self.update()

    def redo(self):
        if not self._redo_stack:
            return
        cmd = self._redo_stack.pop()
        cmd.execute(self)
        self._undo_stack.append(cmd)
        self.update()

    # ── 坐标转换 ──────────────────────────────────────────

    def time_to_x(self, s: float) -> int:
        return int(PADDING + s * self._pixels_per_sec)

    def x_to_time(self, x: int) -> float:
        return max(0.0, (x - PADDING) / self._pixels_per_sec)

    def _track_rect(self, index: int) -> QRectF:
        y = RULER_HEIGHT + index * TRACK_HEIGHT + 2
        t = self._tracks[index]
        x1 = self.time_to_x(t.start)
        x2 = self.time_to_x(t.end)
        return QRectF(x1, y, x2 - x1, TRACK_HEIGHT - 4)

    # ── 选择 ──────────────────────────────────────────────

    def _hit_test(self, pos: QPointF) -> int:
        """判断点击位置命中的轨道索引，-1 表示未命中"""
        for i, t in enumerate(self._tracks):
            if self._track_rect(i).contains(pos):
                return i
        return -1

    def _hit_edge(self, pos: QPointF) -> tuple[int, str] | None:
        """判断是否点击到轨道边缘，返回 (index, side) 或 None"""
        for i, t in enumerate(self._tracks):
            rect = self._track_rect(i)
            left = abs(pos.x() - rect.left())
            right = abs(pos.x() - rect.right())
            if left < TimelineWidget.SnapDistance and rect.top() <= pos.y() <= rect.bottom():
                return (i, "resize_left")
            if right < TimelineWidget.SnapDistance and rect.top() <= pos.y() <= rect.bottom():
                return (i, "resize_right")
        return None

    # ── 鼠标事件 ──────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pos = event.localPos()

        # 点击标尺 → 跳转播放头
        if pos.y() < RULER_HEIGHT:
            self._playhead_s = self.x_to_time(pos.x())
            self._drag_state = "playhead"
            self.update()
            return

        # 边缘检测
        edge = self._hit_edge(pos)
        if edge:
            self._drag_index, self._drag_state = edge
            self._drag_start_x = pos.x()
            t = self._tracks[self._drag_index]
            self._drag_orig_start = t.start
            self._drag_orig_end = t.end
            return

        # 轨道内点击 → 移动或选中
        idx = self._hit_test(pos)
        if idx >= 0:
            self._selected = idx
            self._drag_index = idx
            self._drag_state = "move"
            self._drag_start_x = pos.x()
            t = self._tracks[idx]
            self._drag_orig_start = t.start
            self._drag_orig_end = t.end
            self.update()
            return

        # 点击空白 → 取消选中
        self._selected = -1
        self.update()

    def mouseMoveEvent(self, event):
        if self._drag_state in ("move", "resize_left", "resize_right", "playhead"):
            pos = event.localPos()

            if self._drag_state == "playhead":
                self._playhead_s = self.x_to_time(pos.x())
                self.update()
                return

            t = self._tracks[self._drag_index]
            dt = (pos.x() - self._drag_start_x) / self._pixels_per_sec

            if self._drag_state == "move":
                new_start = max(0.0, self._drag_orig_start + dt)
                new_end = new_start + (self._drag_orig_end - self._drag_orig_start)
                t.start = new_start
                t.end = new_end
            elif self._drag_state == "resize_left":
                new_start = max(0.0, min(self._drag_orig_start + dt, t.end - 0.5))
                t.start = new_start
            elif self._drag_state == "resize_right":
                new_end = max(t.start + 0.5, self._drag_orig_end + dt)
                t.end = new_end

            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        if self._drag_state != "playhead":
            # 生成并压入撤销命令
            cmd = self._make_move_cmd()
            if cmd:
                self._undo_stack.append(cmd)
                self._redo_stack.clear()

        self._drag_state = None
        self._drag_index = -1
        self.update()

    def _make_move_cmd(self) -> MoveClipCommand | None:
        """从拖动状态生成撤销命令"""
        if self._drag_state in ("move", "resize_left", "resize_right"):
            t = self._tracks[self._drag_index]
            if abs(t.start - self._drag_orig_start) > 0.01 or abs(t.end - self._drag_orig_end) > 0.01:
                return MoveClipCommand(
                    track_index=self._drag_index,
                    old_start=self._drag_orig_start, new_start=t.start,
                    old_end=self._drag_orig_end, new_end=t.end,
                )
        return None

    # ── 右键菜单 ──────────────────────────────────────────

    def _show_context_menu(self, pos):
        idx = self._hit_test(pos)
        menu = QMenu(self)
        if idx >= 0:
            menu.addAction("删除轨道", lambda i=idx: self._delete_track(i))
            menu.addAction("拆分", lambda i=idx: self._split_track(i))
            menu.addSeparator()
            menu.addAction("选中", lambda i=idx: setattr(self, '_selected', i) or self.update())
        menu.addAction("全选", self._select_all)
        menu.addAction("清除选中", lambda: setattr(self, '_selected', -1) or self.update())
        menu.exec_(self.mapToGlobal(pos))

    def _delete_track(self, index: int):
        cmd = DeleteClipCommand(track_index=index)
        self._push_undo(cmd)

    def _split_track(self, index: int):
        if self._playhead_s <= self._tracks[index].start or self._playhead_s >= self._tracks[index].end:
            return
        cmd = SplitClipCommand(track_index=index, split_time=self._playhead_s)
        self._push_undo(cmd)

    def _select_all(self):
        self._selected = -2  # 特殊值表示全选
        self.update()

    # ── 键盘事件 ──────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.matches(Qt.Key_Delete) or event.matches(Qt.Key_Backspace):
            if self._selected >= 0:
                self._delete_track(self._selected)
                self._selected = -1
            return
        if event.key() == Qt.Key_S and (event.modifiers() & Qt.ControlModifier) == 0:
            if self._selected >= 0:
                self._split_track(self._selected)
            return
        if event.matches(Qt.Key_Left) and self._selected >= 0:
            t = self._tracks[self._selected]
            cmd = MoveClipCommand(self._selected, t.start, t.start - 0.5, t.end, t.end - 0.5)
            self._push_undo(cmd)
            return
        if event.matches(Qt.Key_Right) and self._selected >= 0:
            t = self._tracks[self._selected]
            cmd = MoveClipCommand(self._selected, t.start, t.start + 0.5, t.end, t.end + 0.5)
            self._push_undo(cmd)
            return
        super().keyPressEvent(event)

    # ── 渲染 ──────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, content_h = self.width(), TIMELINE_HEIGHT + RULER_HEIGHT

        # 背景
        p.fillRect(0, 0, w, content_h, QColor("#2d2d2d"))

        # 标尺
        self._draw_ruler(p)

        # 轨道
        for i, track in enumerate(self._tracks):
            self._draw_track(p, track, i)

        # 播放头
        self._draw_playhead(p)

    def _draw_ruler(self, p: QPainter):
        p.fillRect(0, 0, self.width(), RULER_HEIGHT, QColor("#3d3d3d"))
        p.setPen(QColor("#aaaaaa"))
        p.setFont(QFont("monospace", 9))
        total_px = self._duration * self._pixels_per_sec

        # 刻度间距：自适应
        tick_interval = self._auto_tick_interval()
        t = 0.0
        while t <= self._duration:
            x = self.time_to_x(t)
            if self.time_to_x(t) < self.width():
                p.drawText(int(x), RULER_HEIGHT - 4, self._format_time(t))
                p.setPen(QColor("#666666"))
                p.drawLine(int(x), RULER_HEIGHT, int(x), RULER_HEIGHT + 4)
                p.setPen(QColor("#aaaaaa"))
            t += tick_interval

    def _auto_tick_interval(self) -> float:
        """根据 pixels_per_sec 自动选择刻度间距"""
        for interval in [30, 20, 10, 5, 2, 1, 0.5]:
            if interval * self._pixels_per_sec >= 60:
                return interval
        return 30.0

    def _format_time(self, t: float) -> str:
        m, s = divmod(int(t), 60)
        return f"{m}:{s:02d}"

    def _draw_track(self, p: QPainter, track, index: int):
        rect = self._track_rect(index)
        if rect.width() < 1 or rect.x() + rect.width() < PADDING:
            return

        color = TRACK_COLORS.get(track.type, QColor("#888888"))

        # 选中高亮
        if index == self._selected:
            p.setBrush(QBrush(color.lighter(130)))
            p.setPen(QPen(color.lighter(150), 2))
        else:
            p.setBrush(QBrush(color))
            p.setPen(QPen(color.darker(120), 1))

        p.drawRoundedRect(rect, 3, 3)

        # 轨道标签
        if rect.width() > 40:
            p.setPen(QColor("white"))
            p.setFont(QFont("sans-serif", 8))
            label = f"{track.type}: {track.content[:20]}" if track.content else track.type
            p.drawText(QRectF(rect.x() + 4, rect.y() + 2, rect.width() - 8, rect.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, label)

        # 拖动手柄指示（边缘小方块）
        if index == self._selected or self._drag_index == index:
            p.fillRect(QRectF(rect.x() - 2, rect.y(), 4, rect.height()), QColor("white"))
            p.fillRect(QRectF(rect.right() - 2, rect.y(), 4, rect.height()), QColor("white"))

    def _draw_playhead(self, p: QPainter):
        x = self.time_to_x(self._playhead_s)
        p.setPen(QPen(QColor("#ff4444"), 2))
        p.drawLine(int(x), RULER_HEIGHT, int(x), RULER_HEIGHT + TIMELINE_HEIGHT)

        # 播放头顶部三角
        p.setBrush(QColor("#ff4444"))
        p.setPen(Qt.NoPen)
        tri = QPointF(x - 4, RULER_HEIGHT), QPointF(x + 4, RULER_HEIGHT), QPointF(x, RULER_HEIGHT - 6)
        p.drawPolygon(tri)
