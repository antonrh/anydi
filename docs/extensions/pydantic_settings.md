# Pydantic Settings Extension

The Pydantic Settings extension loads settings from a Pydantic model into an `AnyDI` container.

## Quick Start

If you have a Pydantic `BaseSettings` model for application settings:

```python
from pydantic_settings import BaseSettings
from anydi import Container
import anydi.ext.pydantic_settings


class Settings(BaseSettings):
    app_name: str = "My App"
    debug: bool = False


container = Container()

anydi.ext.pydantic_settings.install(Settings(), container)
```

`anydi.ext.pydantic_settings.install` loads the settings from `Settings` model into the container as singletons.

## Accessing settings

Access settings values from the container:

```python
app_name = container.resolve(Annotated[str, "settings.app_name"])

assert app_name == "My App"
```

## Custom prefix

You can specify a custom prefix for settings:

```python
anydi.ext.pydantic_settings.install(Settings(), container, prefix="my_settings")

app_name = container.resolve(Annotated[str, "my_settings.app_name"])
```
