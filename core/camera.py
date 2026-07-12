"""智能镜头系统 — 速度感知缩放：快速移动缩回全景，停止/点击时放大跟随"""

import math


def minimum_jerk(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5


class CameraSynthesizer:
    """速度感知的镜头系统"""

    FAST_THRESHOLD = 250
    STOP_THRESHOLD = 40
    STOP_DURATION = 0.3
    TRANSITION_DURATION = 0.55
    ZOOM_SCALE = 1.8
    LOOK_AHEAD = 0.12
    LOOK_BEHIND = 0.2
    ZOOM_PRE_ROLL = 0.2
    MIN_ZOOM_HOLD = 2.5
    ACTIVITY_CHAIN_GAP = 1.5
    NEAR_TARGET_RATIO = 0.18
    LARGE_MOVE_RATIO = 0.30
    LARGE_MOVE_SPEED = 400
    MAX_PAN_SPEED_RATIO = 0.75

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

        self._reset_state()
        self._samples = self._compute_samples()
        self._zoomed_segments = self._compute_zoomed_segments()

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

    def _advance(self, ts: float) -> tuple[float, float, float]:
        """按时间顺序推进一次内部镜头状态。"""
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

    def _compute_samples(self) -> list[tuple[float, float, float]]:
        """预计算逐帧镜头轨迹，将有状态逻辑隔离在构建阶段。"""
        self._reset_state()
        frame_count = max(0, math.ceil(self.duration_s * self.fps))
        samples = []
        for index in range(frame_count + 1):
            ts = min(index / self.fps, self.duration_s)
            samples.append(self._advance(ts))
        self._reset_state()
        return samples

    def sample(self, time_ms: float) -> tuple[float, float, float]:
        """按时间随机访问镜头轨迹，调用顺序不影响结果。"""
        ts = max(0.0, time_ms / 1000.0)
        if ts > self.duration_s or not self._samples:
            return (0.5, 0.5, 1.0)

        position = ts * self.fps
        lower = min(int(position), len(self._samples) - 1)
        upper = min(lower + 1, len(self._samples) - 1)
        fraction = position - lower
        if lower == upper or fraction <= 0:
            return self._samples[lower]

        start = self._samples[lower]
        end = self._samples[upper]
        return tuple(
            start[i] + (end[i] - start[i]) * fraction
            for i in range(3)
        )

    def _compute_zoomed_segments(self) -> list[tuple[float, float]]:
        return [(clip.start, clip.end) for clip in self.build_zoom_clips()]

    def _rect_for_target(self, x: float, y: float) -> list[int]:
        divisor = math.gcd(self.w, self.h)
        unit_w = self.w // divisor
        unit_h = self.h // divisor
        scale_units = max(1, round(divisor / self.ZOOM_SCALE))
        zoom_w = min(self.w, unit_w * scale_units)
        zoom_h = min(self.h, unit_h * scale_units)
        left = max(0, min(round(x - zoom_w / 2), self.w - zoom_w))
        top = max(0, min(round(y - zoom_h / 2), self.h - zoom_h))
        return [left, top, zoom_w, zoom_h]

    def _large_motion_between(self, start: float,
                              end: float) -> tuple[float, float] | None:
        """返回两次点击之间持续高速跨屏移动的起止时间。"""
        events = [event for event in self.events if start <= event[0] <= end]
        if len(events) < 2:
            return None

        required_distance = math.hypot(self.w, self.h) * self.LARGE_MOVE_RATIO
        run_start = None
        detected = None
        previous = events[0]
        for current in events[1:]:
            dt = current[0] - previous[0]
            segment_distance = math.hypot(
                current[1] - previous[1], current[2] - previous[2]
            )
            speed = segment_distance / dt if dt > 0 else 0
            if speed >= self.LARGE_MOVE_SPEED:
                if run_start is None:
                    run_start = previous
                net_distance = math.hypot(
                    current[1] - run_start[1], current[2] - run_start[2]
                )
                if net_distance >= required_distance:
                    detected = (run_start[0], current[0])
            else:
                run_start = None
            previous = current
        return detected

    def build_zoom_clips(self) -> list:
        """将点击活动规划为可编辑、区域明确的 Zoom Clip。"""
        from core.project import Clip

        valid_clicks = [
            click for click in self.clicks
            if 0 <= click[0] <= self.duration_s
        ]
        if not valid_clicks:
            return []

        diagonal = math.hypot(self.w, self.h)
        near_distance = diagonal * self.NEAR_TARGET_RATIO
        clips = []

        for click_index, (timestamp, x, y) in enumerate(valid_clicks):
            start = max(0.0, timestamp - self.ZOOM_PRE_ROLL)
            end = min(self.duration_s, timestamp + self.MIN_ZOOM_HOLD)
            rect = self._rect_for_target(x, y)
            candidate = Clip(
                type="zoom", start=start, end=end,
                content="自动缩放", rect=rect,
                transition_duration=self.TRANSITION_DURATION,
            )
            if not clips:
                clips.append(candidate)
                continue

            previous = clips[-1]
            previous_click_time = valid_clicks[click_index - 1][0]
            large_motion = self._large_motion_between(
                previous_click_time, timestamp
            )
            if large_motion:
                previous.end = min(previous.end, large_motion[0])
                candidate.start = max(candidate.start, large_motion[1])
                if previous.end <= previous.start:
                    clips.pop()
                if candidate.end > candidate.start:
                    clips.append(candidate)
                continue

            prev_cx = previous.rect[0] + previous.rect[2] / 2
            prev_cy = previous.rect[1] + previous.rect[3] / 2
            target_distance = math.hypot(x - prev_cx, y - prev_cy)
            candidate.transition_duration = min(
                1.0,
                max(
                    self.TRANSITION_DURATION,
                    target_distance / max(
                        diagonal * self.MAX_PAN_SPEED_RATIO, 1),
                ),
            )
            gap = candidate.start - previous.end

            if gap <= self.ACTIVITY_CHAIN_GAP and target_distance <= near_distance:
                previous.end = max(previous.end, candidate.end)
                continue

            if gap <= self.ACTIVITY_CHAIN_GAP:
                if candidate.start <= previous.end:
                    boundary = max(
                        previous.start + self.TRANSITION_DURATION,
                        candidate.start,
                    )
                else:
                    boundary = previous.end
                previous.end = boundary
                candidate.start = boundary

            clips.append(candidate)

        return clips


def build_camera(clicks: list, fps: int,
                 w: int, h: int, duration_s: float,
                 cursor_events: list = None,
                 base_time: float = 0,
                 monitor_left: int = 0,
                 monitor_top: int = 0) -> CameraSynthesizer:
    click_data = []
    for c in clicks or []:
        t = c.timestamp - base_time
        if t >= 0:
            click_data.append((t, c.x - monitor_left, c.y - monitor_top))

    event_data = []
    for e in cursor_events or []:
        t = e.timestamp - base_time
        if t >= 0:
            event_data.append((t, e.x - monitor_left, e.y - monitor_top))

    if not event_data:
        return CameraSynthesizer(click_data, [], w, h, fps, duration_s)

    return CameraSynthesizer(click_data, event_data, w, h, fps, duration_s)
