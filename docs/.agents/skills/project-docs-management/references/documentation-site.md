# VitePress Documentation Site Guide

Cabbage integrates a full-featured, zero-config VitePress 1.6+ documentation site located at `docs/`.

---

## 1. Project Layout & Architecture

When `cabbage init` is executed, the following VitePress scaffolding is established:

```text
docs/
├── .vitepress/
│   ├── config.ts         # VitePress theme, navbar, and sidebar configuration
│   └── dist/              # Production static build output
├── package.json           # Node.js dependencies (VitePress, Mermaid plugin)
├── pnpm-lock.yaml         # Dependency lockfile
├── README.md              # Documentation site index / homepage
└── [00-22 standard categories]/ # Current-state project documentation
```

---

## 2. Operations & CLI Commands

Cabbage provides convenient wrappers around VitePress commands:

```bash
# 1. Install dependencies (runs pnpm install in docs/)
cabbage docs install

# 2. Start local development server with hot-module reload
cabbage docs dev

# 3. Build production static bundle (outputs to docs/.vitepress/dist/)
cabbage docs build
```

---

## 3. Key Capabilities & Configuration

- **Mermaid Support**: Built-in support for fenced ```mermaid code blocks. Diagrams are dynamically rendered directly in documentation pages.
- **Search**: Built-in local client-side search (MiniSearch) indexed during `docs build`.
- **Auto-Navigation & Sidebar**: Category numbering (`00-overview`, `01-product`, `03-architecture`, etc.) maps cleanly to sidebar navigation groups.
- **GitHub Pages Deployment**: Automated via `.github/workflows/cabbage.yml` on push to default branch.

---

## 4. Troubleshooting Build Failures

If `cabbage docs build` fails:

1. **Dead Links**: VitePress strictly validates local Markdown relative links. Run `cabbage validate --all` to find broken links.
2. **Syntax Errors in Markdown/Mermaid**: Check for unclosed code fences or unmatched HTML tags.
3. **Missing Dependencies**: Re-run `cabbage docs install`.
