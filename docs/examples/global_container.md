# Global container example

This example shows a functional application: plain functions and one adapter, with no service or repository classes. A caching decorator reaches its dependency through the global container, because the module defining the decorator is imported by the container and cannot import it back.

Example application structure:

```
app/
  adapters/
    cache.py
  users/
    services.py
  container.py
  main.py
tests/
  conftest.py
  test_users.py
```

`adapters/cache.py`

Defines the cache protocol, an in-memory implementation and the `cached` decorator, which keys entries by the function name and its arguments. The cache is reached through a global reference, which needs no container.

```python
import functools
from collections.abc import Callable
from typing import Any, Protocol

from anydi import global_ref


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str) -> None: ...


class MemoryCache(Cache):
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value


cache = global_ref(Cache)


def cached(func: Callable[..., str]) -> Callable[..., str]:
    @functools.wraps(func)
    def wrapper(*args: Any) -> str:
        key = ":".join([func.__qualname__, *map(str, args)])

        if (value := cache.get(key)) is not None:
            return value

        value = func(*args)
        cache.set(key, value)
        return value

    return wrapper
```

`users/services.py`

Defines the cached function. It records the users it loaded, so the example can show that the cache works.

```python
from app.adapters.cache import cached

EMAILS = {1: "alice@mail.com", 2: "bob@mail.com"}

loaded: list[int] = []


@cached
def get_user_email(user_id: int) -> str:
    loaded.append(user_id)
    return EMAILS[user_id]
```

`container.py`

Creates the global container and registers the cache implementation. It imports `adapters.cache`, which is why that module cannot import it back.

```python
from anydi import create_global_container

from app.adapters.cache import Cache, MemoryCache

container = create_global_container()


@container.provider(scope="singleton")
def cache_provider() -> Cache:
    return MemoryCache()
```

`main.py`

Calls the function three times for two users. The repeated call is served from the cache, so only two users were loaded.

```python
from app.container import container
from app.users.services import get_user_email, loaded


def main() -> None:
    assert get_user_email(1) == "alice@mail.com"
    assert get_user_email(1) == "alice@mail.com"
    assert get_user_email(2) == "bob@mail.com"

    assert loaded == [1, 2]

    container.close()


if __name__ == "__main__":
    main()
```

`tests/conftest.py`

Imports the application container, so the pytest plugin picks it up as the `container` fixture.

```python
from app.container import container  # noqa: F401
```

`tests/test_users.py`

Overrides the cache. The plugin makes the fixture container the global one, so the decorator resolves the mock.

```python
from unittest import mock

from anydi import Container

from app.adapters.cache import Cache
from app.users.services import get_user_email


def test_get_user_email(container: Container) -> None:
    cache = mock.Mock(spec=Cache)
    cache.get.return_value = "cached@mail.com"

    with container.override(Cache, cache):
        assert get_user_email(1) == "cached@mail.com"

    cache.get.assert_called_once_with("get_user_email:1")
```
