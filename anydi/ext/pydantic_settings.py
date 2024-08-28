from typing import Any, Callable

from pydantic.fields import ComputedFieldInfo, FieldInfo  # noqa
from pydantic_settings import BaseSettings
from typing_extensions import Annotated

from anydi import Container

from ._utils import patch_any_typed_annotated


def install(
    settings: BaseSettings,
    container: Container,
    *,
    prefix: str = ".settings",
    use_any: bool = False,
) -> None:
    """Install Pydantic settings into an AnyDI container."""

    # Ensure prefix ends with a dot
    if prefix[-1] != ".":
        prefix += "."

    def _get_setting_value(setting_value: Any) -> Callable[[], Any]:
        return lambda: setting_value

    all_fields = {**settings.model_fields, **settings.model_computed_fields}
    for setting_name, field_info in all_fields.items():
        if use_any and not isinstance(field_info, (FieldInfo, ComputedFieldInfo)):
            interface: Any = Any
        elif isinstance(field_info, ComputedFieldInfo):
            interface = field_info.return_type
        elif isinstance(field_info, FieldInfo):
            interface = field_info.annotation
        else:
            continue

        container.register(
            Annotated[interface, f"{prefix}{setting_name}"],
            _get_setting_value(getattr(settings, setting_name)),
            scope="singleton",
        )

    if use_any:
        patch_any_typed_annotated(container, prefix=prefix)
