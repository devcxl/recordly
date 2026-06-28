"""智能镜头系统 — 会话式缩放，连续点击不反复 zoom out"""

from dataclasses import dataclass


@dataclass
class CameraTarget:
    time: float
    fx: float
    fy: float
    scale: float


def minimum_jerk(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5


def _make_targets(clicks: list, cursor_events: list,
                  base_time: float) -> list[CameraTarget]:
    targets = []
    for c in clicks:
        t = c.timestamp - base_time
        if t < 0:
            continue
        targets.append(CameraTarget(time=t, fx=c.x, fy=c.y, scale=1.8))
    if not targets and cursor_events:
        base = cursor_events[0].timestamp - base_time
        end = cursor_events[-1].timestamp - base_time
        if end > base:
            count = max(2, int((end - base) // 3))
            for i in range(count + 1):
                t = base + i * (end - base) / count
                cx, cy = cursor_events[0].x, cursor_events[0].y
                for e in cursor_events:
                    if e.timestamp - base_time <= t:
                        cx, cy = e.x, e.y
                targets.append(CameraTarget(
                    time=t, fx=cx, fy=cy, scale=1.6))
    return targets


class CameraSynthesizer:
    """会话式缩放：连续点击保持缩放，间隔>2.5s才 zoom out"""

    SESSION_GAP = 2.5
    ZOOM_IN_DURATION = 0.5
    ZOOM_OUT_DURATION = 0.5

    def __init__(self, targets: list[CameraTarget],
                 w: int, h: int, fps: int):
        self.targets = sorted(targets, key=lambda t: t.time)
        self.width = w
        self.height = h
        self.fps = fps

    def sample(self, time_ms: float) -> tuple[float, float, float]:
        ts = time_ms / 1000
        if not self.targets:
            return (0.5, 0.5, 1.0)

        # 收集所有可能激活的会话
        all_sessions = []
        for t in self.targets:
            s = self._build_session(t)
            if s is None:
                continue
            zoom_in_start = s[0].time - self.ZOOM_IN_DURATION
            zoom_out_end = s[-1].time + self.SESSION_GAP + self.ZOOM_OUT_DURATION
            if zoom_in_start <= ts <= zoom_out_end:
                # 去重：同样的 session 只加一次
                if not all_sessions or s != all_sessions[-1]:
                    all_sessions.append(s)

        if not all_sessions:
            return (0.5, 0.5, 1.0)

        best_scale = 0
        best_state = (0.5, 0.5, 1.0)
        for s in all_sessions:
            st = self._session_state(s, ts)
            if st and st[2] > best_scale:
                best_scale = st[2]
                best_state = st
        return best_state

    def _build_session(self, start_target: CameraTarget):
        """从某个 target 构建其所在会话"""
        try:
            idx = self.targets.index(start_target)
        except ValueError:
            return None
        session = [start_target]
        for t in self.targets[idx + 1:]:
            if t.time - session[-1].time < self.SESSION_GAP:
                session.append(t)
            else:
                break
        for t in reversed(self.targets[:idx]):
            if session[0].time - t.time < self.SESSION_GAP:
                session.insert(0, t)
            else:
                break
        return session

    def _session_state(self, session: list[CameraTarget], ts: float):
        """计算会话在 ts 时刻的镜头状态"""
        if not session:
            return None
        first = session[0]
        last = session[-1]

        zoom_in_start = first.time - self.ZOOM_IN_DURATION
        session_end = last.time + self.SESSION_GAP
        zoom_out_end = session_end + self.ZOOM_OUT_DURATION

        # zoom-in
        if ts < first.time:
            if ts < zoom_in_start:
                return (0.5, 0.5, 1.0)
            p = minimum_jerk((ts - zoom_in_start) / self.ZOOM_IN_DURATION)
            return (
                0.5 + (first.fx - 0.5) * p,
                0.5 + (first.fy - 0.5) * p,
                1.0 + (first.scale - 1.0) * p,
            )

        # zoom-out
        if ts > session_end:
            if ts > zoom_out_end:
                return (0.5, 0.5, 1.0)
            p = minimum_jerk((ts - session_end) / self.ZOOM_OUT_DURATION)
            return (
                last.fx + (0.5 - last.fx) * p,
                last.fy + (0.5 - last.fy) * p,
                last.scale + (1.0 - last.scale) * p,
            )

        # 会话中：多个 target 之间平移
        if len(session) == 1:
            return (first.fx, first.fy, first.scale)

        prev_t = session[0]
        for t in session[1:]:
            if t.time > ts:
                break
            prev_t = t

        if prev_t.time >= ts or prev_t is session[-1]:
            return (prev_t.fx, prev_t.fy, prev_t.scale)

        nxt = session[session.index(prev_t) + 1]
        gap = nxt.time - prev_t.time
        pan = min(0.6, gap * 0.5)
        elapsed = ts - prev_t.time

        if elapsed < pan:
            p = minimum_jerk(elapsed / pan)
            return (
                prev_t.fx + (nxt.fx - prev_t.fx) * p,
                prev_t.fy + (nxt.fy - prev_t.fy) * p,
                prev_t.scale + (nxt.scale - prev_t.scale) * p,
            )
        return (nxt.fx, nxt.fy, nxt.scale)


def build_camera(clicks: list, fps: int,
                 w: int, h: int, duration_s: float,
                 cursor_events: list = None,
                 base_time: float = 0) -> CameraSynthesizer:
    raw = _make_targets(clicks, cursor_events, base_time)
    if not raw:
        return CameraSynthesizer([], w, h, fps)

    merged: list[CameraTarget] = []
    for t in raw:
        if merged and (t.time - merged[-1].time) < 0.3:
            merged[-1] = t
        else:
            merged.append(t)

    for t in merged:
        t.fx /= w
        t.fy /= h

    return CameraSynthesizer(merged, w, h, fps)
