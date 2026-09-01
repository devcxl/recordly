# Project Documentation

此站点由 VuePress 构建，流程由 `cabbage` 约束。

```mermaid
flowchart LR
    Change --> Docs
    Docs --> Validate
    Validate --> Implement
    Implement --> CI
    CI --> Merge
```
