# Basic example

In this example, we are creating a simple application using `PyxDI`. The application has a `User` model, a `UserRepository` and `UserService` that takes an instance of UserRepository as a dependency and provides methods for creating and retrieving users.

Here an example app structure:

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

Defines the data model used in the application, in this case just a simple User model.

```python
import typing as t
import uuid
from dataclasses import dataclass, field

UserId = t.NewType("UserId", uuid.UUID)


@dataclass
class User:
    email: str
    id: UserId = field(default_factory=lambda: UserId(uuid.uuid4()))
```

`repositories.py`

Defines the interface for a UserRepository, which is responsible for accessing and manipulating the User data. It also provides an implementation of this interface using an in-memory data store.

```python
import abc
import typing as t

from app.models import User, UserId


class UserRepository(abc.ABC):
    @abc.abstractmethod
    def all(self) -> t.List[User]:
        pass

    @abc.abstractmethod
    def add(self, user: User) -> None:
        pass

    @abc.abstractmethod
    def get_by_email(self, email: str) -> t.Optional[User]:
        pass


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self.data: t.Dict[UserId, User] = {}

    def all(self) -> t.List[User]:
        return list(self.data.values())

    def add(self, user: User) -> None:
        self.data[user.id] = user

    def get_by_email(self, email: str) -> t.Optional[User]:
        try:
            return [user for user in self.data.values() if user.email == email][0]
        except IndexError:
            return None
```

`services.py`

Defines a UserService class that provides higher-level operations on the User data, such as retrieving all users, creating new users, and retrieving a user by their email address.

```python
import typing as t
from dataclasses import dataclass

from app.models import User
from app.repositories import UserRepository


@dataclass
class UserService:
    user_repository: UserRepository

    def get_users(self) -> t.List[User]:
        return self.user_repository.all()

    def create_user(self, email: str) -> User:
        user = User(email=email)
        self.user_repository.add(user)
        return user

    def get_user(self, email: str) -> t.Optional[User]:
        return self.user_repository.get_by_email(email)
```

`modules.py`

Defines two providers using PyxDI's @provider decorator. The first provider creates an instance of the InMemoryUserRepository class, which is then injected into the UserService provider when it is created.

```python
import pyxdi

from app.repositories import InMemoryUserRepository, UserRepository
from app.services import UserService


class AppModule(pyxdi.Module):
    @pyxdi.provider(scope="singleton")
    def user_repository(self) -> UserRepository:
        return InMemoryUserRepository()

    @pyxdi.provider(scope="singleton")
    def user_service(self, user_repository: UserRepository) -> UserService:
        return UserService(user_repository=user_repository)
```

`handlers.py`

Defines several handlers that use the UserService instance to perform operations on the User data, such as retrieving all users, creating a new user, and retrieving a user by their email address.

```python
import typing as t

import pyxdi

from app.models import User
from app.services import UserService


@pyxdi.inject
def get_users(user_service: UserService = pyxdi.dep) -> t.List[User]:
    return user_service.get_users()


@pyxdi.inject
def get_user(email: str, user_service: UserService = pyxdi.dep) -> User:
    user = user_service.get_user(email)
    if not user:
        raise Exception("User not found.")
    return user


@pyxdi.inject
def create_user(email: str, user_service: UserService = pyxdi.dep) -> User:
    return user_service.create_user(email=email)
```

`main.py`

Creates an instance of the PyxDI class, scans for providers and request handlers, starts the dependency injection container, and runs a small test suite to ensure that everything is working correctly.

```python
import pyxdi

from app.modules import AppModule

di = pyxdi.PyxDI(modules=[AppModule])
di.scan("app.handlers")
di.start()


def main() -> None:
    from app.handlers import create_user, get_user, get_users

    user = create_user(email="demo@mail.com")

    assert get_users() == [user]
    assert get_user(email="demo@mail.com") == user

    di.close()


if __name__ == "__main__":
    main()
```
