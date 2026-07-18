"""UndoCommand.description() 方法测试"""

import pytest
from dataclasses import asdict


class TestUndoCommandDescription:
    """验证各命令子类的 description() 返回预期中文文本"""

    def test_add_clip_description(self):
        from core.commands import AddClipCommand
        cmd = AddClipCommand(
            track_index=0,
            clip_data={"type": "video", "content": "test"},
        )
        assert cmd.description() == "添加片段"

    def test_move_clip_description(self):
        from core.commands import MoveClipCommand
        cmd = MoveClipCommand(
            track_index=0, clip_index=0,
            old_start=0.0, new_start=1.0,
            old_end=5.0, new_end=6.0,
        )
        assert cmd.description() == "移动片段"

    def test_delete_clip_description(self):
        from core.commands import DeleteClipCommand
        cmd = DeleteClipCommand(track_index=0, clip_index=0)
        assert cmd.description() == "删除片段"

    def test_split_clip_description(self):
        from core.commands import SplitClipCommand
        cmd = SplitClipCommand(
            track_index=0, clip_index=0, split_time=2.5,
        )
        assert cmd.description() == "切割片段"

    def test_change_speed_description(self):
        from core.commands import ChangeSpeedCommand
        cmd = ChangeSpeedCommand(
            track_index=0, clip_index=0,
            old_speed=1.0, new_speed=2.0, old_end=5.0,
        )
        assert cmd.description() == "变更速度"


class TestCompositeCommandDescription:
    """CompositeCommand 根据子命令组合推断描述"""

    def test_trim_in_split_delete_left(self):
        """裁剪开头：SplitClipCommand + 删除左半边（clip_index 不变）"""
        from core.commands import SplitClipCommand, DeleteClipCommand, CompositeCommand

        split_cmd = SplitClipCommand(
            track_index=0, clip_index=0, split_time=2.5,
        )
        delete_cmd = DeleteClipCommand(
            track_index=0, clip_index=split_cmd.clip_index,
        )
        composite = CompositeCommand(sub_commands=[split_cmd, delete_cmd])
        assert composite.description() == "裁剪开头"

    def test_trim_out_split_delete_right(self):
        """裁剪结尾：SplitClipCommand + 删除右半边（clip_index + 1）"""
        from core.commands import SplitClipCommand, DeleteClipCommand, CompositeCommand

        split_cmd = SplitClipCommand(
            track_index=0, clip_index=0, split_time=2.5,
        )
        delete_cmd = DeleteClipCommand(
            track_index=0, clip_index=split_cmd.clip_index + 1,
        )
        composite = CompositeCommand(sub_commands=[split_cmd, delete_cmd])
        assert composite.description() == "裁剪结尾"

    def test_generic_composite(self):
        """非裁剪组合 → 批量操作(N步)"""
        from core.commands import AddClipCommand, DeleteClipCommand, CompositeCommand

        add_cmd = AddClipCommand(
            track_index=0,
            clip_data={"type": "video", "content": "test"},
        )
        delete_cmd = DeleteClipCommand(track_index=0, clip_index=0)
        composite = CompositeCommand(sub_commands=[add_cmd, delete_cmd])
        assert composite.description() == "批量操作(2步)"

    def test_single_sub_command_composite(self):
        """单个子命令 → 批量操作(1步)"""
        from core.commands import MoveClipCommand, CompositeCommand

        cmd = MoveClipCommand(
            track_index=0, clip_index=0,
            old_start=0.0, new_start=1.0,
            old_end=5.0, new_end=6.0,
        )
        composite = CompositeCommand(sub_commands=[cmd])
        assert composite.description() == "批量操作(1步)"


class TestDescriptionBackwardCompat:
    """description() 不影响现有 __repr__ 和行为"""

    def test_repr_still_works(self):
        from core.commands import AddClipCommand, MoveClipCommand

        add = AddClipCommand(
            track_index=0,
            clip_data={"type": "video", "content": "test"},
        )
        # AddClipCommand 是 @dataclass，repr 由 dataclass 自动生成（包含所有字段）
        assert "AddClipCommand" in repr(add)
        assert "track_index" in repr(add)

        move = MoveClipCommand(
            track_index=0, clip_index=0,
            old_start=0.0, new_start=1.0,
            old_end=5.0, new_end=6.0,
        )
        # MoveClipCommand 有自定义 __repr__
        assert repr(move) == "MoveClip(t0: 0.0→1.0)"

    def test_default_description_fallback_to_class_name(self):
        """未覆写 description() 的子类默认返回类名"""
        from core.commands import AddClipCommand
        # AddClipCommand 覆写了，但我们可以验证基类的默认行为
        # 直接测试基类：UndoCommand 是抽象类，但 description() 是已实现的
        from core.commands import UndoCommand

        # 通过一个不覆写 description 的子类来验证
        class BareCommand(UndoCommand):
            def execute(self, timeline):
                pass

            def undo(self, timeline):
                pass

        cmd = BareCommand()
        assert cmd.description() == "BareCommand"

    def test_description_non_empty_for_all_subclasses(self):
        """所有 7 个子类的 description() 返回非空字符串"""
        from core.commands import (
            AddClipCommand, MoveClipCommand, DeleteClipCommand,
            SplitClipCommand, ChangeSpeedCommand, CompositeCommand,
        )

        commands = [
            AddClipCommand(track_index=0, clip_data={"type": "video", "content": "test"}),
            MoveClipCommand(track_index=0, clip_index=0, old_start=0.0, new_start=1.0, old_end=5.0, new_end=6.0),
            DeleteClipCommand(track_index=0, clip_index=0),
            SplitClipCommand(track_index=0, clip_index=0, split_time=2.5),
            ChangeSpeedCommand(track_index=0, clip_index=0, old_speed=1.0, new_speed=2.0, old_end=5.0),
            CompositeCommand(sub_commands=[AddClipCommand(track_index=0, clip_data={"type": "video", "content": "test"})]),
        ]

        for cmd in commands:
            desc = cmd.description()
            assert isinstance(desc, str), f"{cmd.__class__.__name__}.description() 应返回 str"
            assert len(desc) > 0, f"{cmd.__class__.__name__}.description() 不应为空"
