# Mermaid Diagram Guidelines & Templates

Mermaid is the official standard for architecture, flow, state, and data relationship diagrams in Cabbage. Diagrams live directly inside Markdown files to enable version tracking and peer review in PRs.

---

## 1. General Principles

1. **Keep Sources in Markdown**: Always write diagrams using ```mermaid fences. Never commit binary images (PNG/JPEG) as the sole source of truth for architectural diagrams.
2. **Text-First & Legible**: Keep node labels concise. Use subgraphs to group bounded contexts or microservices.
3. **Verify Rendering**: Always test diagrams locally via `cabbage docs dev` or during CI builds.

---

## 2. Standard Diagram Templates

### Flowchart (Process & Data Pipelines)

```mermaid
flowchart TD
    subgraph Client["Client Tier"]
        UI["Web / Mobile App"]
    end

    subgraph Gateway["API Gateway"]
        AuthFilter["Auth & Rate Limiting"]
    end

    subgraph Services["Core Microservices"]
        OrderSvc["Order Service"]
        PaymentSvc["Payment Service"]
    end

    subgraph Storage["Data Tier"]
        DB[("PostgreSQL")]
        Redis[("Redis Cache")]
    end

    UI -->|HTTPS / REST| AuthFilter
    AuthFilter --> OrderSvc
    OrderSvc --> Redis
    OrderSvc -->|gRPC| PaymentSvc
    OrderSvc --> DB
```

---

### Sequence Diagram (Call Chains & Protocols)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant App as Web Client
    participant Auth as Auth Service
    participant API as Core API
    participant DB as Database

    User->>App: Input Credentials
    App->>Auth: POST /auth/login
    Auth->>DB: Query User & Verify Hash
    DB-->>Auth: User Record
    Auth-->>App: Return JWT Access & Refresh Token
    App->>API: GET /api/v1/profile (Bearer JWT)
    API-->>App: 200 OK (User Profile)
    App-->>User: Render Dashboard
```

---

### State Diagram (State Machines & Lifecycles)

```mermaid
stateDiagram-v2
    [*] --> Draft: Created
    Draft --> PendingReview: Submit for Review
    PendingReview --> InProgress: Approved
    PendingReview --> Draft: Changes Requested
    InProgress --> Testing: Implementation Complete
    Testing --> Deployed: Tests Passed
    Testing --> InProgress: Defects Found
    Deployed --> Closed: Post-Deploy Verified
    Closed --> [*]
```

---

### ER Diagram (Database Schemas & Relationships)

```mermaid
erDiagram
    TENANT ||--o{ USER : contains
    USER ||--o{ ORDER : places
    ORDER ||--|{ ORDER_ITEM : includes
    PRODUCT ||--o{ ORDER_ITEM : referenced_in

    TENANT {
        uuid id PK
        string name
        string plan
        timestamp created_at
    }
    USER {
        uuid id PK
        uuid tenant_id FK
        string email UK
        string password_hash
        string role
    }
    ORDER {
        uuid id PK
        uuid user_id FK
        decimal total_amount
        string status
        timestamp created_at
    }
    ORDER_ITEM {
        uuid id PK
        uuid order_id FK
        uuid product_id FK
        int quantity
        decimal unit_price
    }
```

---

### Class Diagram (Domain Models & Domain-Driven Design)

```mermaid
classDiagram
    class AggregateRoot {
        <<interface>>
        +getId() String
        +getEvents() List
    }
    class Order {
        -String orderId
        -List~OrderItem~ items
        -OrderStatus status
        +addItem(Product, int) void
        +checkout() void
        +cancel() void
    }
    class OrderItem {
        -String productId
        -int quantity
        -Money price
    }
    AggregateRoot <|.. Order
    Order "1" *-- "many" OrderItem
```

---

### Git Graph (Branching Strategy & Releases)

```mermaid
gitGraph
    commit id: "v1.0.0"
    branch feature/oauth
    checkout feature/oauth
    commit id: "add prd & spec"
    commit id: "impl auth filter"
    checkout main
    merge feature/oauth id: "merge PR #12"
    commit id: "v1.1.0" tag: "v1.1.0"
```
