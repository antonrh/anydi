# Global container

A module that the container imports cannot import the container back, so `container.ref()` is not available there. A decorator or a module-level helper is the usual case.

`create_global_container()` makes a container available process-wide, and `global_ref()` references a dependency without naming it. Prefer `container.ref()` wherever the container can be reached, it says which container it belongs to.

## Example

```python
# app/mail.py
from anydi import global_ref


mailer = global_ref(Mailer)


def send_welcome(email: str) -> None:
    mailer.send(email, "Welcome!")
```

```python
# app/container.py
from anydi import create_global_container

from app.mail import Mailer, SmtpMailer

container = create_global_container()


@container.provider(scope="singleton")
def mailer_provider() -> Mailer:
    return SmtpMailer()
```

A global reference binds on first access, so the modules can be imported in any order. In everything else it behaves like `container.ref()`.

See the [example application](../examples/global_container.md) for a complete application.

## Managing the container

```python
get_global_container()            # raises if it is not set
get_global_container_or_none()    # None instead of raising
set_global_container(container)   # register an existing container
reset_global_container()          # unset it, references bind again
```

There is one global container per process. `create_global_container()` raises if one is already set, so replacing it takes an explicit `reset_global_container()`.

Using a reference while the container is unset raises `RuntimeError` naming the dependency. The reference reports its state without resolving anything:

```
<GlobalRef for app.mail.Mailer, unbound>
```

## Testing

The pytest plugin makes the `container` fixture global, so references resolve against the container under test, `override()` included. A container created with `create_global_container()` is picked up by the fixture, which makes the `anydi_container` setting unnecessary.
