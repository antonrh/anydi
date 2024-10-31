from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Any, Callable

from pydantic.fields import ComputedFieldInfo, FieldInfo  # noqa
from pydantic_settings import BaseSettings

from anydi import Container


def install(
    settings: BaseSettings | Iterable[BaseSettings],
    container: Container,
    *,
    prefix: str = "settings.",
) -> None:
    """Install Pydantic settings into an AnyDI container."""

    # Ensure prefix ends with a dot
    if prefix[-1] != ".":
        prefix += "."

    def _register_settings(_settings: BaseSettings) -> None:
        all_fields = {**_settings.model_fields, **_settings.model_computed_fields}
        for setting_name, field_info in all_fields.items():
            if isinstance(field_info, ComputedFieldInfo):
                interface = field_info.return_type
            elif isinstance(field_info, FieldInfo):
                interface = field_info.annotation
            else:
                continue

            container.register(
                Annotated[interface, f"{prefix}{setting_name}"],
                _get_setting_value(getattr(_settings, setting_name)),
                scope="singleton",
            )

    if isinstance(settings, BaseSettings):
        _register_settings(settings)
    else:
        for _settings in settings:
            _register_settings(_settings)


def _get_setting_value(setting_value: Any) -> Callable[[], Any]:
    return lambda: setting_value
