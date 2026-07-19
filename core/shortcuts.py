"""编辑器快捷键目录和绑定校验。"""

from dataclasses import dataclass
from typing import Literal, Mapping


@dataclass(frozen=True)
class ShortcutAction:
    """一个可配置编辑器操作的固定元数据。"""

    action_id: str
    display_name: str
    category: str
    default_keys: str
    scope: Literal["window", "timeline"]


@dataclass(frozen=True)
class ShortcutValidation:
    """快捷键校验结果。"""

    ok: bool
    code: str | None = None
    conflicting_action_id: str | None = None


_ACTIONS = (
    ShortcutAction("play_pause", "播放/暂停", "播放控制", "Space", "window"),
    ShortcutAction("undo", "撤销", "全局", "Ctrl+Z", "window"),
    ShortcutAction("redo", "重做", "全局", "Ctrl+Shift+Z", "window"),
    ShortcutAction("redo_alt", "重做（备用）", "全局", "Ctrl+Y", "window"),
    ShortcutAction("split_at_playhead", "在播放头处切割", "时间线编辑", "X", "timeline"),
    ShortcutAction("split_selected", "切割选中片段", "时间线编辑", "S", "timeline"),
    ShortcutAction("delete_clip", "删除选中片段", "时间线编辑", "Delete", "timeline"),
    ShortcutAction("delete_clip_alt", "删除选中片段（备用）", "时间线编辑", "Backspace", "timeline"),
    ShortcutAction("trim_in", "裁剪入点", "时间线编辑", "I", "timeline"),
    ShortcutAction("trim_out", "裁剪出点", "时间线编辑", "O", "timeline"),
    ShortcutAction("nudge_left", "微移左移 0.5s", "时间线编辑", "Left", "timeline"),
    ShortcutAction("nudge_right", "微移右移 0.5s", "时间线编辑", "Right", "timeline"),
)
_ACTIONS_BY_ID = {action.action_id: action for action in _ACTIONS}


class ShortcutRegistry:
    """管理固定目录中的当前快捷键绑定。"""

    def __init__(self, bindings: Mapping[str, str] | None = None):
        self._bindings = self._default_bindings()
        if bindings is not None:
            self._bindings.update(
                (action_id, value)
                for action_id, value in bindings.items()
                if action_id in _ACTIONS_BY_ID
            )

    def actions(self, scope: str | None = None) -> tuple[ShortcutAction, ...]:
        """返回全部动作，或指定生效范围的动作。"""
        if scope is None:
            return _ACTIONS
        return tuple(action for action in _ACTIONS if action.scope == scope)

    def binding(self, action_id: str) -> str:
        """返回一个动作的当前 PortableText 绑定。"""
        if action_id not in _ACTIONS_BY_ID:
            raise KeyError("SHORTCUT_UNKNOWN_ACTION")
        return self._bindings[action_id]

    def bindings(self) -> dict[str, str]:
        """返回当前绑定的独立快照。"""
        return dict(self._bindings)

    def validate(self, action_id: str, portable_text: object) -> ShortcutValidation:
        """校验单个绑定，不修改当前映射。"""
        sequence_validation = self._validate_sequence(action_id, portable_text)
        if not sequence_validation.ok:
            return sequence_validation

        for other_action_id, other_binding in self._bindings.items():
            if other_action_id != action_id and other_binding == portable_text:
                return ShortcutValidation(
                    ok=False,
                    code="SHORTCUT_CONFLICT",
                    conflicting_action_id=other_action_id,
                )
        return ShortcutValidation(ok=True)

    def replace_bindings(self, bindings: Mapping[str, object]) -> ShortcutValidation:
        """完整校验后原子替换全部动作绑定。"""
        unknown_action_id = next(
            (action_id for action_id in bindings if action_id not in _ACTIONS_BY_ID),
            None,
        )
        if unknown_action_id is not None:
            return ShortcutValidation(ok=False, code="SHORTCUT_UNKNOWN_ACTION")

        candidate_bindings: dict[str, str] = {}
        for action in _ACTIONS:
            if action.action_id not in bindings:
                return ShortcutValidation(ok=False, code="SHORTCUT_EMPTY_SEQUENCE")

            portable_text = bindings[action.action_id]
            sequence_validation = self._validate_sequence(action.action_id, portable_text)
            if not sequence_validation.ok:
                return sequence_validation
            assert isinstance(portable_text, str)
            candidate_bindings[action.action_id] = portable_text

        conflict_validation = self._validate_conflicts(candidate_bindings)
        if not conflict_validation.ok:
            return conflict_validation

        self._bindings = candidate_bindings
        return ShortcutValidation(ok=True)

    def reset_binding(self, action_id: str) -> ShortcutValidation:
        """将单个动作恢复为默认绑定。"""
        action = _ACTIONS_BY_ID.get(action_id)
        if action is None:
            return ShortcutValidation(ok=False, code="SHORTCUT_UNKNOWN_ACTION")

        validation = self.validate(action_id, action.default_keys)
        if validation.ok:
            self._bindings[action_id] = action.default_keys
        return validation

    def reset_all(self) -> None:
        """将全部动作恢复为默认绑定。"""
        self._bindings = self._default_bindings()

    @staticmethod
    def _default_bindings() -> dict[str, str]:
        return {action.action_id: action.default_keys for action in _ACTIONS}

    @staticmethod
    def _validate_sequence(
        action_id: str,
        portable_text: object,
    ) -> ShortcutValidation:
        if action_id not in _ACTIONS_BY_ID:
            return ShortcutValidation(ok=False, code="SHORTCUT_UNKNOWN_ACTION")
        if not isinstance(portable_text, str):
            return ShortcutValidation(ok=False, code="SHORTCUT_INVALID_SEQUENCE")
        if not portable_text.strip():
            return ShortcutValidation(ok=False, code="SHORTCUT_EMPTY_SEQUENCE")
        return ShortcutValidation(ok=True)

    @staticmethod
    def _validate_conflicts(bindings: Mapping[str, str]) -> ShortcutValidation:
        action_id_by_binding: dict[str, str] = {}
        for action in _ACTIONS:
            binding = bindings[action.action_id]
            conflicting_action_id = action_id_by_binding.get(binding)
            if conflicting_action_id is not None:
                return ShortcutValidation(
                    ok=False,
                    code="SHORTCUT_CONFLICT",
                    conflicting_action_id=conflicting_action_id,
                )
            action_id_by_binding[binding] = action.action_id
        return ShortcutValidation(ok=True)
