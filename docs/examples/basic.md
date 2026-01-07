# Basic example

This example shows how to build a simple application with `AnyDI`. The application has a `User` model, a `UserRepository` and `UserService` that depends on UserRepository instance and provides methods for creating and retrieving users.

Example application structure:

```
app/
  handlers.py
  main.py
  models.py
  modules.py
  repositories.py
  services.py
```

`models.py`

Defines the data model for the application - a simple User model with ID and email fields.

```python
import uuid
from dataclasses import dataclass, field
from typing import NewType

UserId = NewType("UserId", uuid.UUID)


@dataclass(kw_only=True)
class User:
    id: UserId = field(default_factory=lambda: UserId(uuid.uuid4()))
    email: str
```

`repositories.py`

Defines the repository interface for User data access and manipulation. Includes an in-memory implementation of this interface.

```python
import abc

from app.models import User, UserId


class UserRepository(abc.ABC):
    @abc.abstractmethod
    def all(self) -> list[User]:
        pass

    @abc.abstractmethod
    def add(self, user: User) -> None:
        pass

    @abc.abstractmethod
    def get_by_email(self, email: str) -> User | None:
        pass


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self.data: dict[UserId, User] = {}

    def all(self) -> list[User]:
        return list(self.data.values())

    def add(self, user: User) -> None:
        self.data[user.id] = user

    def get_by_email(self, email: str) -> User | None:
        try:
            return [user for user in self.data.values() if user.email == email][0]
        except IndexError:
            return None
```

`services.py`

Defines the UserService class that provides business logic operations - retrieving all users, creating new users, and finding users by email.

```python
from app.models import User
from app.repositories import UserRepository


class UserService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def get_users(self) -> list[User]:
        return self.user_repository.all()

    def create_user(self, email: str) -> User:
        user = User(email=email)
        self.user_repository.add(user)
        return user

    def get_user(self, email: str) -> User | None:
        return self.user_repository.get_by_email(email)
```

`modules.py`

Defines dependency providers using the @provider decorator. The InMemoryUserRepository instance is registered and injected into UserService automatically.

```python
from anydi import Module, provider

from app.repositories import InMemoryUserRepository, UserRepository
from app.services import UserService


class AppModule(Module):
    @provider(scope="singleton")
    def user_repository(self) -> UserRepository:
        return InMemoryUserRepository()

    @provider(scope="singleton")
    def user_service(self, user_repository: UserRepository) -> UserService:
        return UserService(user_repository=user_repository)
```

`handlers.py`

Defines handler functions that use injected UserService to perform operations - getting all users, creating users, and finding users by email.

```python
from anydi import Inject, injectable

from app.models import User
from app.services import UserService


@injectable
def get_users(user_service: UserService = Inject()) -> list[User]:
    return user_service.get_users()


@injectable
def get_user(email: str, user_service: UserService = Inject()) -> User:
    user = user_service.get_user(email)
    if not user:
        raise Exception("User not found.")
    return user


@injectable
def create_user(email: str, user_service: UserService = Inject()) -> User:
    return user_service.create_user(email=email)
```

`main.py`

Creates the Container instance, scans for providers and handlers, starts the DI container, and runs tests to verify the application works correctly.

```python
from anydi import Container

from app.modules import AppModule

container = Container(modules=[AppModule])
container.scan("app.handlers")
container.start()


def main() -> None:
    from app.handlers import create_user, get_user, get_users

    user = create_user(email="demo@mail.com")

    assert get_users() == [user]
    assert get_user(email="demo@mail.com") == user

    container.close()


if __name__ == "__main__":
    main()
```
