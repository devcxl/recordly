"""速度相关纯函数 — 时间映射、碰撞检测、标签格式化"""


def timeline_to_source_time(timeline_ms: float, clip_start_ms: float, speed: float) -> float:
    """时间线时间 → 源时间

    Args:
        timeline_ms: 时间线上的时间位置（毫秒/秒）
        clip_start_ms: clip 起始时间（与 timeline_ms 同单位）
        speed: 播放速度

    Returns:
        对应的源时间位置
    """
    return clip_start_ms + (timeline_ms - clip_start_ms) * speed


def source_to_timeline_time(source_ms: float, clip_start_ms: float, speed: float) -> float:
    """源时间 → 时间线时间

    Args:
        source_ms: 源素材时间位置
        clip_start_ms: clip 起始时间
        speed: 播放速度

    Returns:
        对应的时间线位置
    """
    return clip_start_ms + (source_ms - clip_start_ms) / speed


def get_clip_source_end(clip_start_ms: float, clip_end_ms: float, speed: float) -> float:
    """计算 clip 在源素材中的结束时间

    公式: start + (end - start) * speed
    """
    return clip_start_ms + (clip_end_ms - clip_start_ms) * speed


def plan_clip_speed_change(
    start: float, end: float,
    old_speed: float, new_speed: float,
    next_clip_start: float | None = None,
) -> dict:
    """计划速度变更，返回新的 end 或阻塞原因

    Args:
        start: clip 起始时间
        end: clip 结束时间
        old_speed: 原速度
        new_speed: 新速度
        next_clip_start: 同一轨道下一个 clip 的起始时间（可选）

    Returns:
        {"new_end": float} 或 {"blocked_reason": "clip-overlap"}
    """
    if new_speed <= 0:
        return {"blocked_reason": "invalid-speed"}

    new_end = start + (end - start) * old_speed / new_speed

    if next_clip_start is not None and new_end > next_clip_start:
        return {"blocked_reason": "clip-overlap"}

    return {"new_end": new_end}


def format_speed_label(speed: float) -> str:
    """格式化速度标签

    - 1.0  → ""（不显示）
    - 2.0  → "2x"
    - 1.5  → "1.5x"
    - 0.5  → "0.5x"
    """
    if speed == 1.0:
        return ""
    if speed == int(speed):
        return f"{int(speed)}x"
    # 移除多余的尾随零（保留至少一位小数）
    num = f"{speed:.4f}".rstrip("0").rstrip(".")
    return f"{num}x"
