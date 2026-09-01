# New feature example

```bash
cabbage new feature add-user-login
cabbage impact add-user-login --set api=true --set security=true
cabbage next add-user-login
# edit prd.md
cabbage verify add-user-login requirement
# edit impact.md
cabbage verify add-user-login impact
# continue until gate opens
cabbage gate add-user-login implementation
# implement and verify tasks
cabbage verify add-user-login implementation
cabbage sync add-user-login
cabbage gate add-user-login merge
```
