"""时间线组件 — 支持多 clip 轨道剪辑"""

from dataclasses import asdict
from math import isclose
import os

from PyQt5.QtWidgets import QWidget, QMenu
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush

from core.commands import AddClipCommand, UndoCommand, MoveClipCommand, DeleteClipCommand, SplitClipCommand, ChangeSpeedCommand, CompositeCommand
from core.project import Clip, SPEED_OPTIONS
from core.speed import plan_clip_speed_change, format_speed_label


TRACK_COLORS = {
    "video": QColor("#4A90D9"),
    "audio": QColor("#50C878"),
    "audio_extra": QColor("#2E8B57"),
    "cursor": QColor("#E8A838"),
    "text": QColor("#A855F7"),
    "annotation": QColor("#A855F7"),
    "zoom": QColor("#F97316"),
}
TRACK_HEADER_WIDTH = 80
TRACK_HEIGHT = 48
RULER_HEIGHT = 20
PADDING = 4
CLIP_SNAP_DISTANCE_PX = 8.0


class TimelineWidget(QWidget):
    playhead_changed = pyqtSignal(float)
    zoom_double_clicked = pyqtSignal(float, object)
    zoom_add_requested = pyqtSignal(float)
    zoom_clip_selected = pyqtSignal(object)
    audio_add_requested = pyqtSignal()
    clips_changed = pyqtSignal()
    playhead_seek_play = pyqtSignal(float)
    status_message = pyqtSignal(str)

    SnapDistance = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks = []
        self._playhead_s = 0.0
        self._duration = 60.0
        self._pixels_per_sec = 30.0
        self._selected_track = -1
        self._selected_clip = -1
        self._drag_track = -1
        self._drag_clip = -1
        self._drag_state = None
        self._drag_start_x = 0
        self._drag_orig_start = 0.0
        self._drag_orig_end = 0.0
        self._drag_orig_source_start = 0.0
        self._drag_orig_source_end = None
        self._snap_alignment_time = None
        self._undo_stack = []
        self._redo_stack = []

        self.setMinimumHeight(RULER_HEIGHT + TRACK_HEIGHT + 10)
        self._update_width()
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    @property
    def duration(self) -> float:
        return self._duration

    @duration.setter
    def duration(self, v: float):
        self._duration = max(v, 0.1)
        self._update_width()
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
        self._selected_track = -1
        self._selected_clip = -1
        self._snap_alignment_time = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_height()
        self.update()

    def _update_height(self):
        h = RULER_HEIGHT + len(self._tracks) * TRACK_HEIGHT + 10
        self.setMinimumHeight(h)
        self.setMaximumHeight(h)

    def _update_width(self):
        content_width = TRACK_HEADER_WIDTH + int(
            self._duration * self._pixels_per_sec
        ) + PADDING
        self.setMinimumWidth(content_width)

    @property
    def selected_index(self) -> int:
        """兼容旧接口，返回选中 clip 所在 track 索引"""
        return self._selected_track if self._selected_clip >= 0 else -1

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def _time_to_x(self, s: float) -> int:
        return int(TRACK_HEADER_WIDTH + s * self._pixels_per_sec)

    def _x_to_time(self, x: int) -> float:
        return max(0.0, (x - TRACK_HEADER_WIDTH) / self._pixels_per_sec)

    def _clip_rect(self, track_idx: int, clip_idx: int) -> QRectF:
        track = self._tracks[track_idx]
        clip = track.clips[clip_idx]
        y = RULER_HEIGHT + track_idx * TRACK_HEIGHT + 2
        x1 = self._time_to_x(clip.start)
        x2 = self._time_to_x(clip.end)
        return QRectF(x1, y, x2 - x1, TRACK_HEIGHT - 4)

    def _hit_test(self, pos: QPointF) -> tuple[int, int]:
        for ti, track in enumerate(self._tracks):
            for ci in range(len(track.clips)):
                if self._clip_rect(ti, ci).contains(pos):
                    return ti, ci
        return -1, -1

    def _hit_edge(self, pos: QPointF) -> tuple[int, int, str] | None:
        for ti, track in enumerate(self._tracks):
            for ci in range(len(track.clips)):
                rect = self._clip_rect(ti, ci)
                left = abs(pos.x() - rect.left())
                right = abs(pos.x() - rect.right())
                if left < self.SnapDistance and rect.top() <= pos.y() <= rect.bottom():
                    return ti, ci, "resize_left"
                if right < self.SnapDistance and rect.top() <= pos.y() <= rect.bottom():
                    return ti, ci, "resize_right"
        return None

    # ── 撤销/重做 ─────────────────────────────────────────

    def _push_undo(self, cmd: UndoCommand):
        self._undo_stack.append(cmd)
        self._redo_stack.clear()
        cmd.execute(self)
        self._validate_selection()
        self.clips_changed.emit()
        self.update()

    def undo(self):
        if not self._undo_stack:
            return
        cmd = self._undo_stack.pop()
        cmd.undo(self)
        self._validate_selection()
        self._redo_stack.append(cmd)
        self.clips_changed.emit()
        self.update()

    def redo(self):
        if not self._redo_stack:
            return
        cmd = self._redo_stack.pop()
        cmd.execute(self)
        self._validate_selection()
        self._undo_stack.append(cmd)
        self.clips_changed.emit()
        self.update()

    def _validate_selection(self):
        if self._selected_clip < 0:
            return
        track_exists = 0 <= self._selected_track < len(self._tracks)
        if (track_exists
                and self._selected_clip < len(
                    self._tracks[self._selected_track].clips)):
            return
        self._selected_track = -1
        self._selected_clip = -1

    # ── 鼠标事件 ──────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._snap_alignment_time = None
        pos = event.localPos()

        self._playhead_s = min(self._x_to_time(int(pos.x())), self._duration)
        self._drag_state = "playhead"
        self.update()
        self.playhead_changed.emit(self._playhead_s)

        if pos.y() >= RULER_HEIGHT:
            edge = self._hit_edge(pos)
            if edge:
                self._drag_track, self._drag_clip, self._drag_state = edge
                self._drag_start_x = pos.x()
                clip = self._tracks[self._drag_track].clips[self._drag_clip]
                self._drag_orig_start = clip.start
                self._drag_orig_end = clip.end
                self._drag_orig_source_start = clip.source_start
                self._drag_orig_source_end = clip.source_end
                return

            ti, ci = self._hit_test(pos)
            if ti >= 0 and ci >= 0:
                self._selected_track = ti
                self._selected_clip = ci
                self._drag_track = ti
                self._drag_clip = ci
                self._drag_state = "move"
                self._drag_start_x = pos.x()
                clip = self._tracks[ti].clips[ci]
                self._drag_orig_start = clip.start
                self._drag_orig_end = clip.end
                self._drag_orig_source_start = clip.source_start
                self._drag_orig_source_end = clip.source_end
                if self._tracks[ti].type == "zoom":
                    self.zoom_clip_selected.emit(clip)
                self.update()
                return

            self._selected_track = -1
            self._selected_clip = -1
            self.update()

    def mouseMoveEvent(self, event):
        if self._drag_state in ("move", "resize_left", "resize_right", "playhead"):
            pos = event.localPos()

            if self._drag_state == "playhead":
                self._playhead_s = min(
                    self._x_to_time(int(pos.x())), self._duration)
                self.update()
                self.playhead_changed.emit(self._playhead_s)
                return

            clip = self._tracks[self._drag_track].clips[self._drag_clip]
            dt = (pos.x() - self._drag_start_x) / self._pixels_per_sec

            if self._drag_state == "move":
                clip_duration = self._drag_orig_end - self._drag_orig_start
                new_start = max(0.0, min(
                    self._drag_orig_start + dt,
                    max(0.0, self._duration - clip_duration),
                ))
                new_end = new_start + (self._drag_orig_end - self._drag_orig_start)
                track = self._tracks[self._drag_track]
                new_start, new_end = self._snap_move_candidate(
                    track, self._drag_clip, new_start, new_end)
                clip.start = new_start
                clip.end = new_end
            elif self._drag_state == "resize_left":
                new_start = max(0.0, min(self._drag_orig_start + dt, clip.end - 0.5))
                d_start = new_start - self._drag_orig_start
                clip.start = new_start
                clip.source_start = self._drag_orig_source_start + d_start * clip.speed
            elif self._drag_state == "resize_right":
                new_end = min(
                    self._duration,
                    max(clip.start + 0.5, self._drag_orig_end + dt),
                )
                d_end = new_end - self._drag_orig_end
                clip.end = new_end
                if clip.source_end is not None:
                    clip.source_end = self._drag_orig_source_end + d_end * clip.speed

            self.update()
            return

        # 非拖拽状态 — 边缘 hover 光标
        pos = event.localPos()
        if pos.y() >= RULER_HEIGHT and self._hit_edge(pos):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def _snap_move_candidate(self, track, clip_index: int,
                             start: float, end: float) -> tuple[float, float]:
        self._snap_alignment_time = None
        clip = track.clips[clip_index]
        if self._drag_state != "move" or track.type != "video" or clip.type != "video":
            return start, end

        best = None
        duration = end - start
        max_start = max(0.0, self._duration - duration)
        for index, other in enumerate(track.clips):
            if index == clip_index:
                continue
            candidates = (
                (abs(start - other.end), other.end, other.end),
                (abs(end - other.start), other.start - duration, other.start),
            )
            for distance, snapped_start, target in candidates:
                distance_px = distance * self._pixels_per_sec
                if (distance_px <= CLIP_SNAP_DISTANCE_PX
                        and 0.0 <= snapped_start <= max_start
                        and (best is None or distance_px < best[0])):
                    best = distance_px, snapped_start, target

        if best is None:
            return start, end
        _, snapped_start, self._snap_alignment_time = best
        return snapped_start, snapped_start + duration

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._snap_alignment_time = None

        if self._drag_state not in ("move", "resize_left", "resize_right"):
            self._drag_state = None
            self._drag_track = -1
            self._drag_clip = -1
            self.update()
            return

        cmd = self._make_move_cmd()
        if cmd:
            self._undo_stack.append(cmd)
            self._redo_stack.clear()
            self.clips_changed.emit()

        self._drag_state = None
        self._drag_track = -1
        self._drag_clip = -1
        self.update()

    def mouseDoubleClickEvent(self, event):
        pos = event.localPos()
        ti, ci = self._hit_test(pos)
        if ti < 0 and pos.y() >= RULER_HEIGHT:
            candidate = int((pos.y() - RULER_HEIGHT) // TRACK_HEIGHT)
            if 0 <= candidate < len(self._tracks):
                ti = candidate

        # --- 缩放轨道双击（现有行为，保持不变）---
        if ti >= 0 and self._tracks[ti].type == "zoom":
            clip = self._tracks[ti].clips[ci] if ci >= 0 else None
            self.zoom_double_clicked.emit(min(
                self._x_to_time(int(pos.x())), self._duration), clip)
        # --- 空白区域双击（新增：跳转 + 播放）---
        elif ci < 0 and pos.y() >= RULER_HEIGHT:
            self._playhead_s = min(self._x_to_time(int(pos.x())), self._duration)
            self.update()
            self.playhead_changed.emit(self._playhead_s)
            self.playhead_seek_play.emit(self._playhead_s)
            return

        super().mouseDoubleClickEvent(event)

    def _make_move_cmd(self) -> MoveClipCommand | None:
        if self._drag_state in ("move", "resize_left", "resize_right"):
            clip = self._tracks[self._drag_track].clips[self._drag_clip]
            position_changed = (
                not isclose(clip.start, self._drag_orig_start,
                            abs_tol=1e-9, rel_tol=0.0)
                or not isclose(clip.end, self._drag_orig_end,
                               abs_tol=1e-9, rel_tol=0.0)
            )
            if position_changed:
                return MoveClipCommand(
                    track_index=self._drag_track, clip_index=self._drag_clip,
                    old_start=self._drag_orig_start, new_start=clip.start,
                    old_end=self._drag_orig_end, new_end=clip.end,
                    old_source_start=self._drag_orig_source_start,
                    new_source_start=clip.source_start,
                    old_source_end=self._drag_orig_source_end,
                    new_source_end=clip.source_end,
                )
        return None

    # ── 右键菜单 ──────────────────────────────────────────

    def _build_context_menu(self, pos) -> QMenu:
        ti, ci = self._hit_test(pos)
        if ti < 0 and pos.x() >= TRACK_HEADER_WIDTH and pos.y() >= RULER_HEIGHT:
            candidate = int((pos.y() - RULER_HEIGHT) // TRACK_HEIGHT)
            if 0 <= candidate < len(self._tracks):
                ti = candidate
        menu = QMenu(self)
        if (ti >= 0 and ci < 0 and pos.x() >= TRACK_HEADER_WIDTH
                and self._tracks[ti].type == "zoom"):
            time_s = min(self._x_to_time(int(pos.x())), self._duration)
            menu.addAction(
                "添加缩放块",
                lambda: self.zoom_add_requested.emit(time_s),
            )
        if ti >= 0 and ci >= 0:
            clip = self._tracks[ti].clips[ci]
            menu.addAction("删除", lambda ti=ti, ci=ci: self.delete_clip(ti, ci))
            menu.addAction("拆分", lambda ti=ti, ci=ci: self._split_clip(ti, ci))
            if clip.type == "video":
                speed_menu = menu.addMenu("速度")
                for spd in SPEED_OPTIONS:
                    act = speed_menu.addAction(format_speed_label(spd) or "1x")
                    act.setCheckable(True)
                    act.setChecked(abs(clip.speed - spd) < 0.001)
                    act.triggered.connect(
                        lambda checked, ti=ti, ci=ci, spd=spd: self._change_speed(ti, ci, spd))
            menu.addSeparator()
            menu.addAction("选中", lambda ti=ti, ci=ci: self._select_clip(ti, ci))
        menu.addAction("全选", self._select_all)
        menu.addAction("清除选中", lambda: setattr(self, '_selected_clip', -1) or self.update())
        return menu

    def _show_context_menu(self, pos):
        menu = self._build_context_menu(pos)
        menu.exec_(self.mapToGlobal(pos))

    def _change_speed(self, track_index: int, clip_index: int, new_speed: float):
        clip = self._tracks[track_index].clips[clip_index]
        old_speed = clip.speed
        if abs(old_speed - new_speed) < 0.001:
            return
        next_start = None
        if clip_index + 1 < len(self._tracks[track_index].clips):
            next_start = self._tracks[track_index].clips[clip_index + 1].start
        result = plan_clip_speed_change(clip.start, clip.end, old_speed, new_speed, next_start)
        if "blocked_reason" in result:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "无法变更速度",
                                f"变更速度会与下一个 clip 重叠，请先拆分或移动 clip")
            return
        cmd = ChangeSpeedCommand(track_index, clip_index, old_speed, new_speed, clip.end)
        self._push_undo(cmd)

    def delete_clip(self, track_index: int, clip_index: int):
        cmd = DeleteClipCommand(track_index=track_index, clip_index=clip_index)
        self._push_undo(cmd)

    def add_clip(self, track_index: int, clip: Clip) -> Clip:
        cmd = AddClipCommand(track_index=track_index, clip_data=asdict(clip))
        self._push_undo(cmd)
        assert cmd.clip_index is not None
        self._select_clip(track_index, cmd.clip_index)
        return self._tracks[track_index].clips[cmd.clip_index]

    def _split_clip(self, track_index: int, clip_index: int):
        clip = self._tracks[track_index].clips[clip_index]
        if self._playhead_s <= clip.start or self._playhead_s >= clip.end:
            return
        cmd = SplitClipCommand(track_index=track_index, clip_index=clip_index, split_time=self._playhead_s)
        self._push_undo(cmd)

    def _find_playhead_video(self) -> tuple[int, int] | None:
        for track_index, track in enumerate(self._tracks):
            if track.type != "video":
                continue
            for clip_index, clip in enumerate(track.clips):
                if (clip.type == "video"
                        and clip.start < self._playhead_s < clip.end):
                    return track_index, clip_index
        return None

    def _select_clip(self, track_index: int, clip_index: int):
        self._selected_track = track_index
        self._selected_clip = clip_index
        self.update()

    def _select_all(self):
        self._selected_track = -2
        self._selected_clip = -2
        self.update()

    def trim_in(self):
        """裁掉播放头之前的内容（I 键）。
        对选中 clip：播放头处拆分 → 删除左半边。
        整体作为一个 undo 步。
        """
        if self._selected_clip < 0:
            return
        clip = self._tracks[self._selected_track].clips[self._selected_clip]
        if self._playhead_s <= clip.start:
            return
        if self._playhead_s >= clip.end:
            self.delete_clip(self._selected_track, self._selected_clip)
            self._selected_clip = -1
            return

        split_cmd = SplitClipCommand(
            self._selected_track, self._selected_clip, self._playhead_s)
        delete_cmd = DeleteClipCommand(
            self._selected_track, self._selected_clip)
        self._push_undo(CompositeCommand([split_cmd, delete_cmd]))

    def trim_out(self):
        """裁掉播放头之后的内容（O 键）。
        对选中 clip：播放头处拆分 → 删除右半边。
        """
        if self._selected_clip < 0:
            return
        clip = self._tracks[self._selected_track].clips[self._selected_clip]
        if self._playhead_s >= clip.end:
            return
        if self._playhead_s <= clip.start:
            self.delete_clip(self._selected_track, self._selected_clip)
            self._selected_clip = -1
            return

        split_cmd = SplitClipCommand(
            self._selected_track, self._selected_clip, self._playhead_s)
        delete_cmd = DeleteClipCommand(
            self._selected_track, self._selected_clip + 1)
        self._push_undo(CompositeCommand([split_cmd, delete_cmd]))

    # ── 键盘事件 ──────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_X and event.modifiers() == Qt.NoModifier:
            target = self._find_playhead_video()
            if target is not None:
                self._split_clip(*target)
            else:
                self.status_message.emit("播放头下无视频片段")
            return
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            if self._selected_clip >= 0:
                self.delete_clip(self._selected_track, self._selected_clip)
                self._selected_clip = -1
            return
        if event.key() == Qt.Key_S and (event.modifiers() & Qt.ControlModifier) == 0:
            if self._selected_clip >= 0:
                self._split_clip(self._selected_track, self._selected_clip)
            return
        if event.key() == Qt.Key_I:
            self.trim_in()
            return
        if event.key() == Qt.Key_O:
            self.trim_out()
            return
        if event.key() == Qt.Key_Left and self._selected_clip >= 0:
            clip = self._tracks[self._selected_track].clips[self._selected_clip]
            new_start = max(0.0, clip.start - 0.5)
            shift = new_start - clip.start
            cmd = MoveClipCommand(self._selected_track, self._selected_clip,
                                  clip.start, new_start,
                                  clip.end, clip.end + shift)
            self._push_undo(cmd)
            return
        if event.key() == Qt.Key_Right and self._selected_clip >= 0:
            clip = self._tracks[self._selected_track].clips[self._selected_clip]
            cmd = MoveClipCommand(self._selected_track, self._selected_clip,
                                  clip.start, clip.start + 0.5, clip.end, clip.end + 0.5)
            self._push_undo(cmd)
            return
        super().keyPressEvent(event)

    # ── 渲染 ──────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        content_h = RULER_HEIGHT + len(self._tracks) * TRACK_HEIGHT

        p.fillRect(0, 0, w, content_h + 10, QColor("#2d2d2d"))

        self._draw_ruler(p)

        for i, track in enumerate(self._tracks):
            self._draw_track(p, track, i)

        if self._snap_alignment_time is not None:
            x = self._time_to_x(self._snap_alignment_time)
            p.save()
            p.setRenderHint(QPainter.Antialiasing, False)
            p.setPen(QPen(QColor("#f5c451"), 1, Qt.DashLine))
            p.drawLine(x, RULER_HEIGHT, x, content_h)
            p.restore()

        self._draw_playhead(p)

    def _draw_ruler(self, p: QPainter):
        p.fillRect(0, 0, self.width(), RULER_HEIGHT, QColor("#3d3d3d"))
        p.setPen(QColor("#aaaaaa"))
        p.setFont(QFont("monospace", 9))

        tick_interval = self._auto_tick_interval()
        t = 0.0
        while t <= self._duration:
            x = self._time_to_x(t)
            if x < self.width():
                p.drawText(int(x), RULER_HEIGHT - 4, self._format_time(t))
                p.setPen(QColor("#666666"))
                p.drawLine(int(x), RULER_HEIGHT, int(x), RULER_HEIGHT + 4)
                p.setPen(QColor("#aaaaaa"))
            t += tick_interval
        p.fillRect(0, 0, TRACK_HEADER_WIDTH, RULER_HEIGHT, QColor("#333333"))
        p.setPen(QColor("#888"))
        p.setFont(QFont("sans-serif", 8))
        p.drawText(QRectF(0, 0, TRACK_HEADER_WIDTH, RULER_HEIGHT), Qt.AlignCenter, "时间线")

    def _auto_tick_interval(self) -> float:
        for interval in [30, 20, 10, 5, 2, 1, 0.5]:
            if interval * self._pixels_per_sec >= 60:
                return interval
        return 30.0

    def _format_time(self, t: float) -> str:
        m, s = divmod(int(t), 60)
        return f"{m}:{s:02d}"

    def _draw_track(self, p: QPainter, track, index: int):
        y = RULER_HEIGHT + index * TRACK_HEIGHT

        if index % 2 == 0:
            p.fillRect(0, y, self.width(), TRACK_HEIGHT, QColor("#2a2a2a"))

        p.setPen(QPen(QColor("#383838"), 1))
        p.drawLine(0, y, self.width(), y)
        p.drawLine(0, y + TRACK_HEIGHT, self.width(), y + TRACK_HEIGHT)

        # 轨道头
        header_rect = QRectF(0, y, TRACK_HEADER_WIDTH, TRACK_HEIGHT)
        p.fillRect(header_rect, QColor("#252525"))
        p.setPen(QColor("#aaa"))
        p.setFont(QFont("sans-serif", 9, QFont.Bold))
        p.drawText(QRectF(0, y, TRACK_HEADER_WIDTH, TRACK_HEIGHT),
                   Qt.AlignCenter, track.name or track.type)

        # 所有 clip
        for ci in range(len(track.clips)):
            self._draw_clip(p, track, index, ci)

    def _draw_clip(self, p: QPainter, track, track_idx: int, clip_idx: int):
        clip = track.clips[clip_idx]
        rect = self._clip_rect(track_idx, clip_idx)
        if rect.width() < 1 or rect.x() > self.width():
            return
        if rect.right() < TRACK_HEADER_WIDTH:
            return

        color = TRACK_COLORS.get(clip.type, QColor("#888888"))
        selected = (track_idx == self._selected_track and clip_idx == self._selected_clip)

        if selected:
            p.setBrush(QBrush(color.lighter(130)))
            p.setPen(QPen(color.lighter(150), 2))
        else:
            p.setBrush(QBrush(color))
            p.setPen(QPen(color.darker(120), 1))

        p.drawRoundedRect(rect, 3, 3)

        if rect.width() > 40:
            p.setPen(QColor("white"))
            p.setFont(QFont("sans-serif", 8))
            if clip.type == "audio_extra":
                label = os.path.basename(clip.content) if clip.content else "额外音频"
            else:
                base = f"{clip.type}: {clip.content[:20]}" if clip.content else clip.type
                speed_label = format_speed_label(getattr(clip, 'speed', 1.0))
                label = f"{base} {speed_label}".strip() if speed_label else base
            p.drawText(QRectF(rect.x() + 4, rect.y() + 2, rect.width() - 8, rect.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, label)

        if selected:
            p.fillRect(QRectF(rect.x() - 2, rect.y(), 4, rect.height()), QColor("white"))
            p.fillRect(QRectF(rect.right() - 2, rect.y(), 4, rect.height()), QColor("white"))

    def _draw_playhead(self, p: QPainter):
        x = self._time_to_x(self._playhead_s)
        p.setPen(QPen(QColor("#ff4444"), 2))
        p.drawLine(int(x), RULER_HEIGHT, int(x), RULER_HEIGHT + len(self._tracks) * TRACK_HEIGHT)

        p.setBrush(QColor("#ff4444"))
        p.setPen(Qt.NoPen)
        tri = QPointF(x - 4, RULER_HEIGHT), QPointF(x + 4, RULER_HEIGHT), QPointF(x, RULER_HEIGHT - 6)
        p.drawPolygon(tri)
