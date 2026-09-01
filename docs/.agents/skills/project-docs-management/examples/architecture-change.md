# Architecture change example

```bash
cabbage new architecture split-payment-service
cabbage impact split-payment-service --set api=true --set database=true --set deployment=true
cabbage status split-payment-service
```

The workflow requires impact → RFC → tech spec → ADR → conditional API/DB/security → tests → implementation → release.
