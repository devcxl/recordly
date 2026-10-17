"""FFmpeg 导出共享工具。"""

import logging
import subprocess
import threading

logger = logging.getLogger(__name__)

_gpu_available_cache: bool | None = None


def is_gpu_available() -> bool:
    """检测 CUDA NVENC 是否可用（结果缓存）"""
    global _gpu_available_cache
    if _gpu_available_cache is not None:
        return _gpu_available_cache
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-init_hw_device", "cuda=cuda:0",
             "-f", "lavfi", "-i", "testsrc=duration=0.1:size=320x240:rate=10",
             "-c:v", "h264_nvenc", "-b:v", "1M",
             "-f", "null", "-"],
            capture_output=True, timeout=10,
        )
        _gpu_available_cache = result.returncode == 0
    except Exception:
        _gpu_available_cache = False
    return _gpu_available_cache


def _start_stderr_reader(process):
    """后台线程实时读取 ffmpeg stderr，防止管道缓冲区满阻塞，同时写入临时文件"""
    chunks = []

    def _read():
        try:
            for line in process.stderr:
                text = line.decode("utf-8", errors="replace")
                chunks.append(text)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(text.rstrip())
        except Exception:
            pass
    t = threading.Thread(target=_read, daemon=True)
    t.start()
    return t, chunks

