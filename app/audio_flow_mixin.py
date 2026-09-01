"""音频流程 — MainWindow 拆分之二（issue #143 Step 2）

纯搬移自 app/main_window.py（波形提供/区域同步/补录/额外音频）。
共享 MainWindow 实例状态，通过 Mixin 继承链访问。
"""

import os
import subprocess
from bisect import bisect_left
from dataclasses import asdict
from datetime import datetime
from uuid import uuid4

from PyQt5.QtWidgets import QDialog, QFileDialog

from core.commands import (
    AddClipCommand, ChangeVolumeCommand, CompositeCommand,
)
from core.project import AudioRegion, Clip, Track, sync_audio_regions_from_clips
from app.project_restore_mixin import _read_wav
from ui.record_audio_dialog import RecordAudioDialog


class AudioFlowMixin:
    """音频轨道提供/同步/补录/额外音频。"""

    def _track_audio_provider(self, track_type: str):
        """按轨提供波形数据：取该轨首个 clip 的 source_path 读 wav（结果缓存）。

        仅 audio/audio_system 内置轨提供波形；audio_extra 轨返回 None（不绘制）。
        录制后文件尚未写入时（_populate_timeline 先于 _finalize_project），
        回退到内存中的 mic/system 录音数据，保证录制后立即播放即有波形。
        """
        if track_type not in ("audio", "audio_system"):
            return None
        for track in self._timeline.tracks:
            if track.type != track_type:
                continue
            if not track.clips:
                continue
            if track.clips[0].source_path:
                source_path = track.clips[0].source_path
                if source_path not in self._track_audio_cache:
                    self._track_audio_cache[source_path] = _read_wav(source_path)
                result = self._track_audio_cache[source_path]
                if result is None:
                    return None
                return result.data, result.samplerate
            # 回退：录制刚结束、wav 尚未写盘 → 用内存录音数据
            if self._recorded_data:
                key = "mic_audio" if track_type == "audio" else "system_audio"
                audio = self._recorded_data.get(key)
                if audio is not None and len(audio.data) > 0:
                    return audio.data, audio.samplerate
        return None
        return None

    def _sync_audio_regions(self):
        """把时间线三轨（audio/audio_system/audio_extra）clip 同步进 _audio_regions"""
        audio_clips = [
            c for t in self._timeline.tracks
            if t.type in ("audio", "audio_system", "audio_extra")
            for c in t.clips
        ]
        self._audio_regions = sync_audio_regions_from_clips(
            audio_clips, self._audio_regions)

    def _on_re_record_requested(self, track_index: int, clip_index: int):
        """麦克风补录：录音窗口 → 写 wav → 原 clip 静音 + 插入新 clip（单步撤销）。

        失败/取消零残留：对话框取消不写文件；写盘失败删除已写文件。
        """
        if not self._project_dir:
            self._show_notification("补录音频", "请先打开项目再补录音频", "warning")
            return

        dialog = RecordAudioDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        result = dialog.audio_result
        if result is None:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = os.path.join(self._project_dir, f"re_record_{timestamp}.wav")
        try:
            from app.main_window import _write_wav
            _write_wav(wav_path, result.data, result.samplerate)
        except Exception as exc:
            try:
                os.remove(wav_path)
            except OSError:
                pass
            self._show_notification("补录音频失败", str(exc), "error")
            return

        target = self._timeline.tracks[track_index].clips[clip_index]
        duration = len(result.data) / result.samplerate
        clip_end = min(target.end, target.start + duration)
        new_clip = Clip(
            type="audio",
            start=target.start,
            end=clip_end,
            source_start=0.0,
            source_end=clip_end - target.start,
            source_path=wav_path,
            volume=1.0,
            content="补录音频",
        )
        clips = self._timeline.tracks[track_index].clips
        insert_at = bisect_left([c.start for c in clips], new_clip.start)
        cmd = CompositeCommand([
            ChangeVolumeCommand(track_index, clip_index,
                                target.volume, 0.0),
            AddClipCommand(track_index, asdict(new_clip),
                           clip_index=insert_at),
        ])
        self._timeline.push_command(cmd)

    # ── Inspector / volume 交互 ─────────────────────────

    def _on_add_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "添加额外音频轨道", "",
            "音频文件 (*.mp3 *.wav *.aac *.m4a *.flac *.ogg)")
        if not path:
            return

        duration_s = self._get_audio_duration(path)
        if duration_s <= 0:
            self._show_notification(
                "无法读取音频",
                f"无法获取文件时长: {os.path.basename(path)}",
                "warning",
            )
            return

        playhead_ms = int(self._timeline.playhead * 1000)
        duration_ms = min(
            int(duration_s * 1000),
            max(0, int(self._timeline.duration * 1000) - playhead_ms),
        )
        if duration_ms <= 0:
            return

        region = AudioRegion(
            id=str(uuid4()),
            start_ms=playhead_ms,
            end_ms=playhead_ms + duration_ms,
            source_start_ms=0,
            source_end_ms=duration_ms,
            audio_path=path,
            volume=1.0,
            name=os.path.basename(path),
        )
        self._audio_regions.append(region)
        self._update_audio_timeline()

        self._show_notification(
            "已添加音频",
            f"{region.name} ({duration_s:.1f}s)",
            "success",
        )

    def _get_audio_duration(self, filepath: str) -> float:
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries',
                 'format=duration', '-of',
                 'default=noprint_wrappers=1:nokey=1', filepath],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return 0.0

    def _update_audio_timeline(self):
        self._timeline.set_tracks([
            t for t in self._timeline.tracks if t.type != "audio_extra"
        ], clear_history=False)

        if self._audio_regions:
            clips = []
            for r in self._audio_regions:
                clips.append(Clip(
                    id=r.id,
                    type="audio_extra",
                    content=r.name,
                    start=r.start_ms / 1000.0,
                    end=r.end_ms / 1000.0,
                    source_start=r.source_start_ms / 1000.0,
                    source_end=(
                        r.source_end_ms / 1000.0
                        if r.source_end_ms is not None else None
                    ),
                    source_path=r.audio_path,
                    volume=r.volume,
                ))
            track = Track(type="audio_extra", name="额外音频", clips=clips)
            self._timeline.tracks.append(track)

        self._timeline._update_height()
        self._timeline.update()

    # ── 菜单操作 ──────────────────────────────────────────
