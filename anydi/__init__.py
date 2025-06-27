"""AnyDI public objects and functions."""

from ._container import Container
from ._decorators import injectable, provided, provider, request, singleton, transient
from ._module import Module
from ._provider import ProviderDef as Provider
from ._scope import Scope
from ._typing import Marker

# Alias for dependency auto marker
auto = Marker()


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
    "provided",
]
