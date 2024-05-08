from __future__ import annotations

from typing import Sequence

from django.conf import settings
from typing_extensions import TypedDict


class Settings(TypedDict):
    CONTAINER_FACTORY: str | None
    STRICT_MODE: bool
    REGISTER_SETTINGS: bool
    REGISTER_COMPONENTS: bool
    INJECT_URLCONF: str | None
    MODULES: Sequence[str]
    SCAN_PACKAGES: Sequence[str]
    PATCH_NINJA: bool


DEFAULTS = Settings(
    CONTAINER_FACTORY=None,
    STRICT_MODE=False,
    REGISTER_SETTINGS=False,
    REGISTER_COMPONENTS=False,
    MODULES=[],
    PATCH_NINJA=False,
    INJECT_URLCONF=None,
    SCAN_PACKAGES=[],
)


def get_settings() -> Settings:
    """Get the AnyDI settings from the Django settings."""
    return Settings(
        **{
            **DEFAULTS,
            **getattr(settings, "ANYDI", {}),
        }
    )
