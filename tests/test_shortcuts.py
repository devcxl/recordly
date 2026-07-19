"""Tests for core/shortcuts.py"""

import pytest

from core.shortcuts import ShortcutRegistry


EXPECTED_ACTIONS = {
    "play_pause": ("window", "Space"),
    "undo": ("window", "Ctrl+Z"),
    "redo": ("window", "Ctrl+Shift+Z"),
    "redo_alt": ("window", "Ctrl+Y"),
    "split_at_playhead": ("timeline", "X"),
    "split_selected": ("timeline", "S"),
    "delete_clip": ("timeline", "Delete"),
    "delete_clip_alt": ("timeline", "Backspace"),
    "trim_in": ("timeline", "I"),
    "trim_out": ("timeline", "O"),
    "nudge_left": ("timeline", "Left"),
    "nudge_right": ("timeline", "Right"),
}


class TestShortcutRegistry:
    def test_catalog_contains_twelve_unique_actions_and_defaults(self):
        registry = ShortcutRegistry()

        actions = registry.actions()

        assert len(actions) == 12
        assert {
            action.action_id: (action.scope, action.default_keys)
            for action in actions
        } == EXPECTED_ACTIONS
        assert len({action.default_keys for action in actions}) == 12

    def test_actions_filter_by_scope(self):
        registry = ShortcutRegistry()

        assert [action.action_id for action in registry.actions("window")] == [
            "play_pause",
            "undo",
            "redo",
            "redo_alt",
        ]
        assert [action.action_id for action in registry.actions("timeline")] == [
            "split_at_playhead",
            "split_selected",
            "delete_clip",
            "delete_clip_alt",
            "trim_in",
            "trim_out",
            "nudge_left",
            "nudge_right",
        ]

    def test_binding_returns_snapshot_and_rejects_unknown_action(self):
        registry = ShortcutRegistry()

        snapshot = registry.bindings()
        snapshot["undo"] = "Ctrl+K"

        assert registry.binding("undo") == "Ctrl+Z"
        with pytest.raises(KeyError, match="SHORTCUT_UNKNOWN_ACTION"):
            registry.binding("missing")

    def test_validate_allows_current_binding_and_rejects_invalid_changes(self):
        registry = ShortcutRegistry()

        assert registry.validate("undo", "Ctrl+Z").ok

        unknown = registry.validate("missing", "Ctrl+K")
        empty = registry.validate("undo", "")
        conflict = registry.validate("undo", "Ctrl+Y")

        assert unknown.code == "SHORTCUT_UNKNOWN_ACTION"
        assert empty.code == "SHORTCUT_EMPTY_SEQUENCE"
        assert conflict.code == "SHORTCUT_CONFLICT"
        assert conflict.conflicting_action_id == "redo_alt"

    def test_reset_binding_respects_conflicts_and_reset_all_restores_defaults(self):
        registry = ShortcutRegistry()
        bindings = registry.bindings()
        bindings["undo"] = "Ctrl+K"
        assert registry.replace_bindings(bindings).ok

        assert registry.reset_binding("undo").ok
        assert registry.binding("undo") == "Ctrl+Z"

        bindings = registry.bindings()
        bindings["play_pause"] = "Ctrl+Z"
        bindings["undo"] = "Ctrl+K"
        assert registry.replace_bindings(bindings).ok

        conflict = registry.reset_binding("undo")
        assert conflict.code == "SHORTCUT_CONFLICT"
        assert registry.binding("undo") == "Ctrl+K"

        registry.reset_all()
        assert registry.bindings() == {
            action_id: default_keys
            for action_id, (_scope, default_keys) in EXPECTED_ACTIONS.items()
        }

    def test_replace_bindings_is_atomic(self):
        registry = ShortcutRegistry()
        original_bindings = registry.bindings()
        replacement = registry.bindings()
        replacement["undo"] = "Ctrl+K"
        replacement["redo"] = "Ctrl+K"

        result = registry.replace_bindings(replacement)

        assert result.code == "SHORTCUT_CONFLICT"
        assert result.conflicting_action_id == "undo"
        assert registry.bindings() == original_bindings
