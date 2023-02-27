from .core import DependencyParam, PyxDI
from .decorators import inject, provider, request, singleton, transient

dep = DependencyParam()

__all__ = [
    "PyxDI",
    "dep",
    "inject",
    "provider",
    "request",
    "singleton",
    "transient",
]
