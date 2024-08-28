from typing import Any

from pydantic import computed_field
from pydantic_settings import BaseSettings
from typing_extensions import Annotated

import anydi.ext.pydantic_settings
from anydi import Container


class Settings(BaseSettings):
    param_str: str = "test"
    param_int: int = 42
    param_float: float = 3.14

    @computed_field
    def param_computed(self) -> str:
        return "computed"


def test_get_settings() -> None:
    container = Container()

    anydi.ext.pydantic_settings.install(Settings(), container, prefix="settings")

    assert container.resolve(Annotated[str, "settings.param_str"]) == "test"
    assert container.resolve(Annotated[int, "settings.param_int"]) == 42
    assert container.resolve(Annotated[float, "settings.param_float"]) == 3.14
    assert container.resolve(Annotated[str, "settings.param_computed"]) == "computed"


def test_get_settings_use_any() -> None:
    container = Container(strict=False)

    anydi.ext.pydantic_settings.install(
        Settings(),
        container,
        prefix="settings",
        use_any=True,
    )

    assert container.resolve(Annotated[Any, "settings.param_str"]) == "test"
    assert container.resolve(Annotated[Any, "settings.param_int"]) == 42
    assert container.resolve(Annotated[Any, "settings.param_float"]) == 3.14
    assert container.resolve(Annotated[Any, "settings.param_computed"]) == "computed"
