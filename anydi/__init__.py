"""AnyDI public objects and functions."""

from ._container import Container
from ._decorators import injectable, provider, request, singleton, transient
from ._module import Module
from ._provider import ProviderDefinition as Provider
from ._scope import Scope
from ._test import TestContainer
from ._utils import Marker

# Alias for dependency auto marker
auto = Marker()


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
