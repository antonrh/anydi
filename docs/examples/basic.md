# Basic example

```
app/
  handlers.py
  main.py
  models.py
  repositories.py
  services.py
```

`models.py`

```python
from dataclasses import dataclass


@dataclass
class User:
    email: str
```

`repositories.py`

```python
from app.models import User


class UserRepository:
    def __init__(self) -> None:


    def add(self, user: User) -> None:
        pass
```
