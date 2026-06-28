"""时间线编辑器 — 基于 QGraphicsScene"""

from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsItem, QWidget, QVBoxLayout, QScrollBar,
    QMenu,
)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QLineF
from PyQt5.QtGui import (
    QPen, QBrush, QColor, QPainter, QFont, QLinearGradient,
)

from app.constants import (
    TIMELINE_PIXELS_PER_SECOND as PPS,
    DEFAULT_TRACK_HEIGHT,
    DEFAULT_RULER_HEIGHT,
)
from core.project import Project, Track


class ClipItem(QGraphicsRectItem):
    """时间线上的剪辑片段"""

    def __init__(self, track: Track, track_index: int,
                 x: float, y: float, w: float, color: str = "#4a9eff"):
        super().__init__(0, 0, w, DEFAULT_TRACK_HEIGHT - 4)
        self.track = track
        self.track_index = track_index
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(QColor(color), 1))
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        # 左右裁切手柄
        self._drag_handle = None  # "left" / "right"

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        # 绘制标签
        painter.setPen(QColor("white"))
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        text = self.track.content if self.track.content else self.track.type
        painter.drawText(self.rect().adjusted(4, 0, 0, 0),
                         Qt.AlignVCenter | Qt.AlignLeft, text)

    def mousePressEvent(self, event):
        # 检查是否在裁切手柄区域
        local = event.pos()
        if local.x() <= 6:
            self._drag_handle = "left"
        elif local.x() >= self.rect().width() - 6:
            self._drag_handle = "right"
        else:
            self._drag_handle = None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_handle = None
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            # 限制在轨道内
            if isinstance(value, QPointF):
                track_top = DEFAULT_RULER_HEIGHT + self.track_index * DEFAULT_TRACK_HEIGHT
                value.setY(track_top)
        return super().itemChange(change, value)

    @property
    def start_time(self) -> float:
        return self.pos().x() / PPS

    @property
    def end_time(self) -> float:
        return (self.pos().x() + self.rect().width()) / PPS

    def set_time_range(self, start: float, end: float):
        self.setPos(start * PPS, self.pos().y())
        self.setRect(0, 0, (end - start) * PPS, DEFAULT_TRACK_HEIGHT - 4)
        self.track.start = start
        self.track.end = end


class Playhead(QGraphicsItem):
    """播放头（红线）"""

    def __init__(self, scene_height: float, parent=None):
        super().__init__(parent)
        self._height = scene_height
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setCursor(Qt.SizeHorCursor)

    def boundingRect(self) -> QRectF:
        return QRectF(-1, 0, 3, self._height)

    def paint(self, painter, option, widget):
        painter.setPen(QPen(QColor("#ff4444"), 2))
        painter.drawLine(QLineF(0, 0, 0, self._height))

    def set_scene_height(self, h: float):
        self._height = h
        self.prepareGeometryChange()
