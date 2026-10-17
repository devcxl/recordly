"""光标与缩放采样 — Compositor 的方法扩展。"""

import bisect


class CursorZoomMixin:
    """光标/点击事件、缩放区域与坐标变换。"""

    def load_cursor_events(self, events: list, clicks: list):
        self._cursor_events = events or []
        self._click_events = []
        for e in clicks or []:
            self._click_events.append((e.x, e.y, e.timestamp - self._base_time))

    def set_monitor_offset(self, left: int, top: int):
        """设置显示器在屏幕坐标系中的偏移量"""
        self._monitor_left = left
        self._monitor_top = top

    def set_cursor(self, x: int, y: int, state: str = "idle"):
        self._cursor_x = max(0, min(x, self.width))
        self._cursor_y = max(0, min(y, self.height))
        self._cursor_state = state

    def add_click(self, x: int, y: int, ts: float):
        self._click_events.append((x, y, ts))

    def set_zoom(self, rect: tuple | None):
        self._zoom_rect = rect
        self.clear_preview_cache()

    def _interpolate_cursor(self, ts: float) -> tuple[int, int]:
        """根据帧时间戳插值出当前帧的鼠标位置（减去显示器偏移得到帧内坐标）"""
        if not self._cursor_events:
            return self._cursor_x, self._cursor_y
        events = self._cursor_events
        target = self._base_time + ts
        if target <= events[0].timestamp:
            x, y = events[0].x, events[0].y
        elif target >= events[-1].timestamp:
            x, y = events[-1].x, events[-1].y
        else:
            # 二分查找目标时间戳
            lo, hi = 0, len(events) - 1
            while lo < hi:
                mid = (lo + hi) // 2
                if events[mid].timestamp < target:
                    lo = mid + 1
                else:
                    hi = mid
            i = lo
            e0, e1 = events[i - 1], events[i]
            if e1.timestamp == e0.timestamp:
                x, y = e1.x, e1.y
            else:
                t = (target - e0.timestamp) / (e1.timestamp - e0.timestamp)
                x = int(e0.x + (e1.x - e0.x) * t)
                y = int(e0.y + (e1.y - e0.y) * t)
        return x - self._monitor_left, y - self._monitor_top

    def _interpolate_cursor_raw(self, rel_ts: float) -> tuple[int, int]:
        """按相对时间插值光标位置（用于 keyframe 生成）"""
        target = self._base_time + rel_ts
        events = self._cursor_events
        if not events:
            return self._cursor_x, self._cursor_y
        if target <= events[0].timestamp:
            x, y = events[0].x, events[0].y
        elif target >= events[-1].timestamp:
            x, y = events[-1].x, events[-1].y
        else:
            for i in range(1, len(events)):
                if events[i].timestamp >= target:
                    e0, e1 = events[i - 1], events[i]
                    if e1.timestamp == e0.timestamp:
                        x, y = e1.x, e1.y
                    else:
                        t = (target - e0.timestamp) / (e1.timestamp - e0.timestamp)
                        x = int(e0.x + (e1.x - e0.x) * t)
                        y = int(e0.y + (e1.y - e0.y) * t)
                    break
            else:
                x, y = events[-1].x, events[-1].y
        return x - self._monitor_left, y - self._monitor_top

    def _get_zoom_at(self, ts: float,
                     source_ts: float | None = None) -> tuple | None:
        if self._manual_zoom_clips is not None:
            if not self._manual_zoom_clips:
                return None
            starts = [c.start for c in self._manual_zoom_clips]
            i = bisect.bisect_right(starts, ts) - 1
            if i >= 0:
                c = self._manual_zoom_clips[i]
                if ts <= c.end and c.rect:
                    target = tuple(c.rect)
                    duration = max(0.0, c.end - c.start)
                    transition = min(
                        max(0.0, getattr(c, "transition_duration", 0.4)),
                        duration / 2,
                    )
                    if transition <= 0:
                        return target

                    full = (0, 0, self.width, self.height)
                    previous = full
                    if i > 0:
                        prev_clip = self._manual_zoom_clips[i - 1]
                        if (prev_clip.rect
                                and c.start - prev_clip.end <= 0.001):
                            previous = tuple(prev_clip.rect)

                    elapsed = ts - c.start
                    if elapsed < transition:
                        return self._interpolate_rect(
                            previous, target, elapsed / transition)

                    remaining = c.end - ts
                    if remaining < transition:
                        if i + 1 < len(self._manual_zoom_clips):
                            next_clip = self._manual_zoom_clips[i + 1]
                            if (next_clip.rect
                                    and next_clip.start - c.end <= 0.001):
                                # 相邻 Clip 的平移由下一个 Clip 入场过渡完成，
                                # 避免当前 Clip 先移动一次导致边界跳变。
                                return target
                        return self._interpolate_rect(
                            target, full,
                            1.0 - remaining / transition,
                        )
                    return target
            return None
        if not self._camera:
            return None
        w, h = self.width, self.height
        camera_ts = ts if source_ts is None else source_ts
        fx, fy, scale = self._camera.sample(camera_ts * 1000)
        zw = int(w / scale)
        zh = int(h / scale)
        zx = int(fx * w - zw / 2)
        zy = int(fy * h - zh / 2)
        zx = max(0, min(zx, w - zw))
        zy = max(0, min(zy, h - zh))
        return (zx, zy, zw, zh)

    @staticmethod
    def _interpolate_rect(start: tuple, end: tuple,
                          progress: float) -> tuple[int, int, int, int]:
        progress = max(0.0, min(1.0, progress))
        eased = 10 * progress ** 3 - 15 * progress ** 4 + 6 * progress ** 5
        return tuple(round(a + (b - a) * eased)
                     for a, b in zip(start, end))

    @staticmethod
    def _transform_point(x: int, y: int, width: int, height: int,
                         zoom: tuple | None = None,
                         crop_rect: tuple | None = None) -> tuple[int, int]:
        if zoom:
            zx, zy, zw, zh = zoom
            x = int((x - zx) * width / max(zw, 1))
            y = int((y - zy) * height / max(zh, 1))
        if crop_rect:
            crop_x, crop_y, crop_w, crop_h = crop_rect
            x = int((x - crop_x) * width / max(crop_w, 1))
            y = int((y - crop_y) * height / max(crop_h, 1))
        return x, y

