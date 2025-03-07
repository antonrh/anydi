"""AnyDI public objects and functions."""

from typing import Any, cast

from ._container import (
    Container,
    Module,
    injectable,
    provider,
    request,
    singleton,
    transient,
)
from ._types import Marker, ProviderArgs as Provider, Scope

# Alias for dependency auto marker
auto = cast(Any, Marker())


__all__ = [
    "Container",
    "Module",
    "Provider",
    "Scope",
    "auto",
    "injectable",
    "provider",
    "request",
    "singleton",
    "transient",
]
