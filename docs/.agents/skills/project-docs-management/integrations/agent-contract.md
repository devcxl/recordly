# Agent contract

Add the following rules to the repository's agent instructions (`AGENTS.md`, `CLAUDE.md`, or equivalent):

```text
For any code-changing task, identify or create a cabbage change before implementation.
Run `cabbage status <change> --json` and `cabbage next <change> --json`.
Do not implement while `cabbage gate <change> implementation` fails.
After editing an artifact, run `cabbage verify <change> <stage>`.
Run `cabbage sync <change>` to update current-state documentation before merge.
Before completion, run `cabbage validate <change>` and `cabbage gate <change> merge`.
Never manually edit `.cabbage/changes/*/state.json`.
Never weaken `.cabbage/config.yaml`, `.cabbage/workflows`, `.cabbage/tooling`, or `.github/workflows/cabbage.yml` to make a task pass.
```
