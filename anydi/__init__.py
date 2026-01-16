"""AnyDI public objects and functions."""

from ._container import Container, import_container
from ._decorators import injectable, provided, provider, request, singleton, transient
from ._marker import Inject, Provide
from ._module import Module
from ._provider import ProviderDef as Provider
from ._types import Scope

# Alias for dependency auto marker
# TODO: deprecate it
auto = Inject()


__all__ = [
    "Container",
    "Inject",
    "Module",
    "Provide",
    "Provider",
    "Scope",
    "auto",
    "import_container",
    "injectable",
    "provided",
    "provider",
    "request",
    "singleton",
    "transient",
]
