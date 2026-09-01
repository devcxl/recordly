# Test report

Validated during packaging:

- Python source compilation
- Workflow YAML parsing
- VuePress `package.json` JSON parsing
- `cabbage init`
- `cabbage new feature`
- implementation gate blocks incomplete workflow
- `complete` stage validation
- completed upstream artifact edit propagates `stale` downstream
- conditional impact activation
- impact table synchronization
- Git diff CI rejects code-only changes without a bound change
- CI requires current-state docs for impacted domains
- CI passes a fully completed/bound change
- archive workflow and archived-history CI handling
- vendored `.cabbage/tooling/cabbage_cli` execution
- unit test suite

Not executed in the packaging container:

- `pnpm install`
- full VuePress production build

The packaging container has no npm registry access. VuePress dependencies are scaffolded for installation in the target project.
