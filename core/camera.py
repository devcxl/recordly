"""智能镜头系统 — 速度感知缩放：快速移动缩回全景，停止/点击时放大跟随"""


def minimum_jerk(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5


class CameraSynthesizer:
    """速度感知的镜头系统

    鼠标大幅快速移动 → 缩回全景（观众看上下文）
    鼠标停止/点击     → 放大跟随鼠标位置（看细节）
    """

    FAST_THRESHOLD = 250        # px/s，超过此速度判定为快速移动
    STOP_THRESHOLD = 40         # px/s，低于此速度判定为停止
    STOP_DURATION = 0.3         # 秒，停止持续多久后开始 zoom in
    TRANSITION_DURATION = 0.35  # 秒，过渡动画时长
    ZOOM_SCALE = 1.8            # zoom in 放大倍数
    LOOK_AHEAD = 0.12           # 计算速度时的前向窗口
    LOOK_BEHIND = 0.2           # 计算速度时的后向窗口

    def __init__(self, clicks: list, cursor_events: list,
                 w: int, h: int, fps: int, duration_s: float):
        self.clicks = sorted(clicks, key=lambda c: c[0]) if clicks else []
        self.events = sorted(cursor_events, key=lambda c: c[0]) if cursor_events else []
        self.w = w
        self.h = h
        self.fps = fps
        self.duration_s = duration_s

        self._from_state = (0.5, 0.5, 1.0)
        self._to_state = (0.5, 0.5, 1.0)
        self._trans_start = -1.0
        self._last_fast_ts = -10.0
        self._last_state = (0.5, 0.5, 1.0)

        self._zoomed_segments = self._compute_zoomed_segments()
        self._reset_state()

    def _reset_state(self):
        self._from_state = (0.5, 0.5, 1.0)
        self._to_state = (0.5, 0.5, 1.0)
        self._trans_start = -1.0
        self._last_fast_ts = -10.0
        self._last_state = (0.5, 0.5, 1.0)

    @property
    def zoomed_segments(self) -> list[tuple[float, float]]:
        return self._zoomed_segments

    def _interpolate(self, ts: float) -> tuple[float, float]:
        if not self.events:
            return (self.w * 0.5, self.h * 0.5)
        prev = self.events[0]
        for e in self.events:
            if e[0] > ts:
                break
            prev = e
        if prev[0] >= ts:
            return (prev[1], prev[2])
        nxt = None
        for e in self.events:
            if e[0] > ts:
                nxt = e
                break
        if nxt is None:
            return (prev[1], prev[2])
        t = (ts - prev[0]) / (nxt[0] - prev[0])
        return (prev[1] + (nxt[1] - prev[1]) * t,
                prev[2] + (nxt[2] - prev[2]) * t)

    def _calc_speed(self, ts: float) -> float:
        if len(self.events) < 2:
            return 0
        t0 = ts - self.LOOK_BEHIND
        t1 = ts + self.LOOK_AHEAD
        p0 = self._interpolate(t0)
        p1 = self._interpolate(t1)
        dt = t1 - t0
        if dt <= 0:
            return 0
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        return (dx * dx + dy * dy) ** 0.5 / dt

    def _has_click(self, ts: float):
        for c in self.clicks:
            if abs(c[0] - ts) < 0.05:
                return c
        return None

    def sample(self, time_ms: float) -> tuple[float, float, float]:
        ts = time_ms / 1000.0
        if ts > self.duration_s:
            return (0.5, 0.5, 1.0)

        target = self._to_state

        click = self._has_click(ts)
        if click:
            target = (click[1] / self.w, click[2] / self.h, self.ZOOM_SCALE)

        speed = self._calc_speed(ts)

        if speed > self.FAST_THRESHOLD:
            self._last_fast_ts = ts
            target = (0.5, 0.5, 1.0)
        elif ts - self._last_fast_ts > self.STOP_DURATION and speed < self.STOP_THRESHOLD:
            px, py = self._interpolate(ts)
            target = (px / self.w, py / self.h, self.ZOOM_SCALE)

        if target != self._to_state:
            self._from_state = self._last_state
            self._to_state = target
            self._trans_start = ts

        if self._trans_start >= 0:
            dt = ts - self._trans_start
            progress = min(1.0, dt / self.TRANSITION_DURATION)
            p = minimum_jerk(progress)
            self._last_state = (
                self._from_state[0] + (self._to_state[0] - self._from_state[0]) * p,
                self._from_state[1] + (self._to_state[1] - self._from_state[1]) * p,
                self._from_state[2] + (self._to_state[2] - self._from_state[2]) * p,
            )
            if progress >= 1.0:
                self._trans_start = -1
        else:
            self._last_state = self._to_state

        return self._last_state

    def _compute_zoomed_segments(self) -> list[tuple[float, float]]:
        if self.duration_s <= 0:
            return []
        segments = []
        in_zoom = False
        seg_start = 0.0
        step = 1.0 / self.fps
        ts = 0.0
        while ts <= self.duration_s:
            _, _, scale = self.sample(ts * 1000)
            if scale > 1.05:
                if not in_zoom:
                    seg_start = ts
                    in_zoom = True
            else:
                if in_zoom:
                    segments.append((seg_start, ts))
                    in_zoom = False
            ts += step
        if in_zoom:
            segments.append((seg_start, self.duration_s))
        # 合并间隔小于 0.3s 的相邻段
        if not segments:
            return segments
        merged = [segments[0]]
        for s, e in segments[1:]:
            if s - merged[-1][1] < 0.3:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))
        return merged


def build_camera(clicks: list, fps: int,
                 w: int, h: int, duration_s: float,
                 cursor_events: list = None,
                 base_time: float = 0) -> CameraSynthesizer:
    click_data = []
    for c in clicks or []:
        t = c.timestamp - base_time
        if t >= 0:
            click_data.append((t, c.x, c.y))

    event_data = []
    for e in cursor_events or []:
        t = e.timestamp - base_time
        if t >= 0:
            event_data.append((t, e.x, e.y))

    if not event_data:
        return CameraSynthesizer(click_data, [], w, h, fps, duration_s)

    return CameraSynthesizer(click_data, event_data, w, h, fps, duration_s)
