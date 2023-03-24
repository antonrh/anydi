from .core import Dependency, PyxDI
from .decorators import inject, provider, request, singleton, transient

dep = Dependency()

__all__ = [
    "PyxDI",
    "dep",
    "inject",
    "provider",
    "request",
    "singleton",
    "transient",
]
