"""AnyDI public objects and functions."""

from typing import Any, cast

from ._container import Container
from ._decorators import injectable, provider, request, singleton, transient
from ._module import Module
from ._provider import ProviderDefinition as Provider
from ._scope import Scope
from ._test import TestContainer
from ._types import Marker

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
