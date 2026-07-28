"""AnyDI public objects and functions."""

from ._container import Container, import_container
from ._decorators import injectable, provided, provider, request, singleton, transient
from ._global import (
    create_global_container,
    get_global_container,
    get_global_container_or_none,
    global_ref,
    reset_global_container,
    set_global_container,
)
from ._marker import Inject, Provide
from ._module import Module
from ._provider import ProviderDef as Provider
from ._types import Scope

__all__ = [
    "Container",
    "Inject",
    "Module",
    "Provide",
    "Provider",
    "Scope",
    "create_global_container",
    "get_global_container",
    "get_global_container_or_none",
    "global_ref",
    "import_container",
    "injectable",
    "provided",
    "provider",
    "request",
    "reset_global_container",
    "set_global_container",
    "singleton",
    "transient",
]
