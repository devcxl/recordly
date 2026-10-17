"""预览区域缩放框叠加层。"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget


class ZoomOverlay(QWidget):
    """预览区域上的缩放框叠加层（坐标 = 合成器分辨率）"""

    rect_changed = pyqtSignal(int, int, int, int)

    HANDLE_MARGIN = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rect = None
        self._comp_size = (1920, 1080)
        self._dragging = False
        self._resize_edge: str | None = None
        self._drag_start = (0, 0)
        self._drag_orig = (0, 0, 0, 0)
        self.hide()

    def set_rect(self, x, y, w, h, comp_w=1920, comp_h=1080):
        self._rect = (x, y, w, h)
        self._comp_size = (comp_w, comp_h)
        self.show()
        self.update()

    def clear_rect(self):
        self._rect = None
        self.hide()

    def _label_rect(self):
        """返回 label 内 pixmap 的显示矩形（像素坐标）"""
        p = self.parent().pixmap() if self.parent() else None
        if not p or p.isNull():
            return (0, 0, self.width(), self.height())
        pw, ph = p.width(), p.height()
        lw, lh = self.width(), self.height()
        ox = max(0, (lw - pw) // 2)
        oy = max(0, (lh - ph) // 2)
        return (ox, oy, pw, ph)

    def _comp_to_widget(self, cx, cy):
        """合成坐标 → widget 坐标"""
        ox, oy, dw, dh = self._label_rect()
        cw, ch = self._comp_size
        if cw <= 0 or ch <= 0:
            return (cx, cy)
        return (int(ox + cx * dw / cw), int(oy + cy * dh / ch))

    def _widget_to_comp(self, wx, wy):
        """widget 坐标 → 合成坐标"""
        ox, oy, dw, dh = self._label_rect()
        cw, ch = self._comp_size
        if dw <= 0 or dh <= 0:
            return (wx, wy)
        return (int((wx - ox) * cw / dw), int((wy - oy) * ch / dh))

    def paintEvent(self, event):
        if not self._rect:
            return
        p = QPainter(self)
        x1, y1 = self._comp_to_widget(self._rect[0], self._rect[1])
        x2, y2 = self._comp_to_widget(self._rect[0] + self._rect[2],
                                       self._rect[1] + self._rect[3])
        p.setPen(QPen(QColor("#00ccff"), 2))
        p.setBrush(QBrush(QColor(0, 204, 255, 30)))
        p.drawRect(x1, y1, x2 - x1, y2 - y1)
        p.setPen(QColor("#00ccff"))
        p.drawText(x1 + 4, y1 + 14, "缩放区域")
        p.setBrush(QBrush(QColor("#00ccff")))
        handle = 8
        for hx, hy in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)):
            p.drawRect(hx - handle // 2, hy - handle // 2,
                       handle, handle)

    def _hit_test(self, wx, wy):
        """在 widget 坐标中命中具体边/角，保持可操作区域宽度稳定。"""
        if not self._rect:
            return None
        x, y, w, h = self._rect
        left_x, top_y = self._comp_to_widget(x, y)
        right_x, bottom_y = self._comp_to_widget(x + w, y + h)
        margin = self.HANDLE_MARGIN
        left = abs(wx - left_x) <= margin
        right = abs(wx - right_x) <= margin
        top = abs(wy - top_y) <= margin
        bottom = abs(wy - bottom_y) <= margin

        if top and left:
            return "top_left"
        if top and right:
            return "top_right"
        if bottom and left:
            return "bottom_left"
        if bottom and right:
            return "bottom_right"
        if (left_x + margin <= wx <= right_x - margin
                and top_y + margin <= wy <= bottom_y - margin):
            return "move"
        return None

    @staticmethod
    def _cursor_for_hit(hit: str | None):
        if hit in ("top_left", "bottom_right"):
            return Qt.SizeFDiagCursor
        if hit in ("top_right", "bottom_left"):
            return Qt.SizeBDiagCursor
        if hit == "move":
            return Qt.SizeAllCursor
        return Qt.ArrowCursor

    def _resize_from_corner(self, edge: str,
                            pointer: tuple[int, int]) -> tuple[int, int, int, int]:
        x, y, width, height = self._drag_orig
        comp_w, comp_h = self._comp_size
        aspect = comp_w / max(comp_h, 1)

        anchor_x = x + width if "left" in edge else x
        anchor_y = y + height if "top" in edge else y
        width_from_pointer = abs(pointer[0] - anchor_x)
        height_from_pointer = abs(pointer[1] - anchor_y)
        scale_x = width_from_pointer / max(width, 1)
        scale_y = height_from_pointer / max(height, 1)
        scale = (scale_x if abs(scale_x - 1) >= abs(scale_y - 1)
                 else scale_y)

        horizontal_limit = anchor_x if "left" in edge else comp_w - anchor_x
        vertical_limit = anchor_y if "top" in edge else comp_h - anchor_y
        max_width = max(1, min(horizontal_limit, vertical_limit * aspect))
        min_width = min(max_width, max(20, round(20 * aspect)))
        new_width = round(max(min_width, min(width * scale, max_width)))
        new_height = max(1, round(new_width / aspect))

        new_x = anchor_x - new_width if "left" in edge else anchor_x
        new_y = anchor_y - new_height if "top" in edge else anchor_y
        return new_x, new_y, new_width, new_height

    def mousePressEvent(self, event):
        if not self._rect or event.button() != Qt.LeftButton:
            return
        hit = self._hit_test(event.x(), event.y())
        if hit:
            self._dragging = hit == "move"
            self._resize_edge = None if hit == "move" else hit
            self._drag_start = self._widget_to_comp(event.x(), event.y())
            self._drag_orig = self._rect

    def mouseMoveEvent(self, event):
        if not self._rect:
            return
        if not self._dragging and not self._resize_edge:
            self.setCursor(self._cursor_for_hit(
                self._hit_test(event.x(), event.y())))
            return
        cw, ch = self._comp_size
        comp = self._widget_to_comp(event.x(), event.y())
        dx = comp[0] - self._drag_start[0]
        dy = comp[1] - self._drag_start[1]
        x, y, w, h = self._drag_orig

        if self._dragging:
            new_x = max(0, min(x + dx, cw - w))
            new_y = max(0, min(y + dy, ch - h))
            self._rect = (new_x, new_y, w, h)
            self.update()
        elif self._resize_edge:
            self._rect = self._resize_from_corner(self._resize_edge, comp)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._dragging or self._resize_edge:
            self._dragging = False
            self._resize_edge = None
            if self._rect:
                self.rect_changed.emit(*self._rect)

