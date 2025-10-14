from typing import Annotated

from pydantic import computed_field
from pydantic_settings import BaseSettings

import anydi.ext.pydantic_settings
from anydi import Container


class Settings(BaseSettings):
    param_str: str = "test"
    param_int: int = 42
    param_float: float = 3.14

    @computed_field
    def param_computed(self) -> str:
        return "computed"


class DBSettings(BaseSettings):
    db_url: str = "sqlite://:memory:"


def test_install_settings() -> None:
    container = Container()

    anydi.ext.pydantic_settings.install(Settings(), container, prefix="settings")

    assert container.resolve(Annotated[str, "settings.param_str"]) == "test"
    assert container.resolve(Annotated[int, "settings.param_int"]) == 42
    assert container.resolve(Annotated[float, "settings.param_float"]) == 3.14
    assert container.resolve(Annotated[str, "settings.param_computed"]) == "computed"


def test_install_multiple_settings() -> None:
    container = Container()

    anydi.ext.pydantic_settings.install(
        [Settings(), DBSettings()], container, prefix="settings."
    )

    assert container.resolve(Annotated[str, "settings.param_str"]) == "test"
    assert container.resolve(Annotated[str, "settings.db_url"]) == "sqlite://:memory:"
