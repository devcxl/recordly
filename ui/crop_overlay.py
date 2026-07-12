"""裁剪叠加层 — 在预览上显示可拖拽的裁剪框（归一化坐标 0-1）"""

try:
    from PyQt5.QtWidgets import QWidget
    from PyQt5.QtCore import Qt, pyqtSignal
    from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
    _HAS_QT = True
except ImportError:
    _HAS_QT = False

    class QWidget:
        pass

    class Qt:
        LeftButton = 1
        SizeHorCursor = 6
        SizeVerCursor = 7
        ArrowCursor = 0

    class QPainter:
        Antialiasing = 4

    class QColor:
        pass

    class QPen:
        pass

    class QBrush:
        pass

    class QPainterPath:
        pass

    pyqtSignal = None


class CropOverlay(QWidget):
    """裁剪叠加层 — 显示可拖拽的裁剪框，坐标归一化 0-1

    四条边可独立拖拽：
      - top/bottom → 垂直拖拽（改变 y / height）
      - left/right  → 水平拖拽（改变 x / width）

    遮罩：裁剪框外半透明黑色 (60% opacity)
    边框：#2563EB, 3px
    最小尺寸：归一化 0.1
    """

    crop_changed = pyqtSignal(float, float, float, float)  # x, y, w, h 归一化

    HANDLE_MARGIN = 8   # 像素，边缘点击敏感区
    MIN_CROP = 0.1      # 归一化最小值

    def __init__(self, parent=None):
        super().__init__(parent)
        self._crop = (0.0, 0.0, 1.0, 1.0)
        self._dragging_edge: str | None = None
        self._drag_start = (0.0, 0.0)
        self._drag_orig = (0.0, 0.0, 1.0, 1.0)
        self.setMouseTracking(True)
        self.hide()

    # ── 公开接口 ──────────────────────────────────────────────

    def set_crop(self, x: float, y: float, w: float, h: float):
        """设置裁剪区域并显示叠加层"""
        self._crop = (x, y, w, h)
        self.show()
        self.update()

    def clear_crop(self):
        """重置为全屏 (0, 0, 1, 1) 并隐藏"""
        self._crop = (0.0, 0.0, 1.0, 1.0)
        self.hide()

    @property
    def crop(self) -> tuple[float, float, float, float]:
        return self._crop

    # ── 坐标映射 ──────────────────────────────────────────────

    def _label_rect(self):
        """label 内 pixmap 的显示矩形 (ox, oy, dw, dh) 像素坐标"""
        p = self.parent().pixmap() if self.parent() else None
        if not p or p.isNull():
            return (0, 0, self.width(), self.height())
        pw, ph = p.width(), p.height()
        lw, lh = self.width(), self.height()
        ox = max(0, (lw - pw) // 2)
        oy = max(0, (lh - ph) // 2)
        return (ox, oy, pw, ph)

    def _norm_to_widget(self, nx: float, ny: float) -> tuple[int, int]:
        """归一化坐标 → widget 像素坐标"""
        ox, oy, dw, dh = self._label_rect()
        if dw <= 0 or dh <= 0:
            return (int(nx * self.width()), int(ny * self.height()))
        return (int(ox + nx * dw), int(oy + ny * dh))

    def _widget_to_norm(self, wx: int, wy: int) -> tuple[float, float]:
        """widget 像素坐标 → 归一化坐标"""
        ox, oy, dw, dh = self._label_rect()
        if dw <= 0 or dh <= 0:
            return (0.0, 0.0)
        return ((wx - ox) / dw, (wy - oy) / dh)

    def _crop_rect_widget(self):
        """裁剪框在 widget 坐标中的矩形 (x, y, w, h)"""
        x1, y1 = self._norm_to_widget(self._crop[0], self._crop[1])
        x2, y2 = self._norm_to_widget(
            self._crop[0] + self._crop[2], self._crop[1] + self._crop[3]
        )
        return (x1, y1, x2 - x1, y2 - y1)

    # ── 绘制 ──────────────────────────────────────────────────

    def paintEvent(self, event):
        if not _HAS_QT:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        cx, cy, cw, ch = self._crop_rect_widget()

        # 外部半透明遮罩（裁剪框外区域）
        path = QPainterPath()
        path.addRect(self.rect())
        inner = QPainterPath()
        inner.addRect(cx, cy, cw, ch)
        mask = path - inner
        p.fillPath(mask, QBrush(QColor(0, 0, 0, 153)))  # 60% opacity

        # 蓝色边框
        pen = QPen(QColor("#2563EB"), 3)
        p.setPen(pen)
        p.setBrush(QBrush())
        p.drawRect(cx, cy, cw, ch)

    # ── 命中检测 ──────────────────────────────────────────────

    def _hit_test_edge(self, nx: float, ny: float) -> str | None:
        """返回命中的边缘 'top'/'bottom'/'left'/'right' 或 None"""
        x, y, w, h = self._crop
        ox, oy, dw, dh = self._label_rect()
        if dw <= 0 or dh <= 0:
            return None
        nmx = self.HANDLE_MARGIN / dw
        nmy = self.HANDLE_MARGIN / dh

        if abs(ny - y) < nmy and x - nmx <= nx <= x + w + nmx:
            return "top"
        if abs(ny - (y + h)) < nmy and x - nmx <= nx <= x + w + nmx:
            return "bottom"
        if abs(nx - x) < nmx and y - nmy <= ny <= y + h + nmy:
            return "left"
        if abs(nx - (x + w)) < nmx and y - nmy <= ny <= y + h + nmy:
            return "right"
        return None

    @staticmethod
    def _get_cursor_for_edge(edge: str | None):
        if edge in ("left", "right"):
            return Qt.SizeHorCursor
        if edge in ("top", "bottom"):
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    # ── 鼠标事件 ──────────────────────────────────────────────

    def mouseMoveEvent(self, event):
        nx, ny = self._widget_to_norm(event.x(), event.y())

        if self._dragging_edge:
            dx = nx - self._drag_start[0]
            dy = ny - self._drag_start[1]
            x, y, w, h = self._drag_orig

            if self._dragging_edge == "top":
                new_y = max(0.0, min(y + dy, y + h - self.MIN_CROP))
                new_h = y + h - new_y
                self._crop = (x, new_y, w, new_h)
            elif self._dragging_edge == "bottom":
                new_h = max(self.MIN_CROP, min(h + dy, 1.0 - y))
                self._crop = (x, y, w, new_h)
            elif self._dragging_edge == "left":
                new_x = max(0.0, min(x + dx, x + w - self.MIN_CROP))
                new_w = x + w - new_x
                self._crop = (new_x, y, new_w, h)
            elif self._dragging_edge == "right":
                new_w = max(self.MIN_CROP, min(w + dx, 1.0 - x))
                self._crop = (x, y, new_w, h)

            self.update()
        else:
            edge = self._hit_test_edge(nx, ny)
            self.setCursor(self._get_cursor_for_edge(edge))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        nx, ny = self._widget_to_norm(event.x(), event.y())
        edge = self._hit_test_edge(nx, ny)
        if edge:
            self._dragging_edge = edge
            self._drag_start = (nx, ny)
            self._drag_orig = self._crop

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._dragging_edge:
            self._dragging_edge = None
            self.crop_changed.emit(*self._crop)
