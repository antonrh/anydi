"""AnyDI public objects and functions."""

from ._container import Container
from ._decorators import injectable, provided, provider, request, singleton, transient
from ._module import Module
from ._provider import ProviderDef as Provider
from ._scope import Scope
from ._typing import Inject, InjectMarker

# Alias for dependency injection marker
auto = InjectMarker()


__all__ = [
    "Container",
    "Inject",
    "Module",
    "Provider",
    "Scope",
    "auto",
    "injectable",
    "provided",
    "provider",
    "request",
    "singleton",
    "transient",
]
