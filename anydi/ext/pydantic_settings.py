from __future__ import annotations

try:
    import pydantic_settings  # noqa: F401
except ImportError:  # pragma: no cover - CI installs it
    message = (
        "This extension needs `pydantic-settings`. "
        "Install it with `pip install pydantic-settings`."
    )
    raise ImportError(message) from None

from collections.abc import Callable, Iterable
from typing import Annotated, Any

from pydantic.fields import ComputedFieldInfo, FieldInfo
from pydantic_settings import BaseSettings

from anydi import Container


def install(
    settings: BaseSettings | Iterable[BaseSettings],
    container: Container,
    *,
    prefix: str = "settings.",
    override: bool = False,
) -> None:
    """Install Pydantic settings into an AnyDI container."""

    # Ensure prefix ends with a dot
    if prefix[-1] != ".":
        prefix += "."

    def _register_settings(_settings: BaseSettings) -> None:
        settings_cls = type(_settings)
        all_fields = {**settings_cls.model_fields, **settings_cls.model_computed_fields}
        for setting_name, field_info in all_fields.items():
            if isinstance(field_info, ComputedFieldInfo):
                origin = field_info.return_type
            elif isinstance(field_info, FieldInfo):
                origin = field_info.annotation
            else:
                continue

            interface = f"{prefix}{setting_name}"
            try:
                container.register(
                    Annotated[origin, interface],
                    _get_setting_value(getattr(_settings, setting_name)),
                    scope="singleton",
                    override=override,
                )
            except LookupError:
                # Say which field collided, not just which annotation.
                raise LookupError(
                    f"`{settings_cls.__name__}.{setting_name}` is already "
                    f"registered as `{interface}`. Install it under another "
                    "`prefix`, or pass `override=True` to replace it."
                ) from None

    if isinstance(settings, BaseSettings):
        _register_settings(settings)
    else:
        for _settings in settings:
            _register_settings(_settings)


def _get_setting_value(setting_value: Any) -> Callable[[], Any]:
    return lambda: setting_value
