"""AnyDI public objects and functions."""

from typing import Any, cast

from ._container import Container
from ._decorators import injectable, provider, request, singleton, transient
from ._module import Module
from ._test import TestContainer
from ._types import Marker, ProviderArgs as Provider, Scope

# Alias for dependency auto marker
auto = cast(Any, Marker())


__all__ = [
    "Container",
    "Module",
    "Provider",
    "Scope",
    "TestContainer",
    "auto",
    "injectable",
    "provider",
    "request",
    "singleton",
    "transient",
]
