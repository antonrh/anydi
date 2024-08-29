# Pydantic Settings Extension

The Pydantic Settings extension allows you to load settings from a Pydantic model into an AnyDI container.

## Quick Start

Suppose you have a Pydantic `BaseSettings` model for your application settings:

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

`anydi.ext.pydantic_settings.install` will load the settings from the `Settings` model into the container as singletons.

## Accessing Settings

You can access the settings values from the container like this:

```python
app_name = container.resolve(Annotated[str, "settings.app_name"])

assert app_name == "My App"
```

## Custom Prefix

You can also specify a custom prefix for the settings:

```python
anydi.ext.pydantic_settings.install(Settings(), container, prefix="my_settings")

app_name = container.resolve(Annotated[str, "my_settings.app_name"])
```
