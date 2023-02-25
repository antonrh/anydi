from .core import DependencyParam, PyxDI
from .decorators import request, singleton, transient

dep = DependencyParam()

__all__ = [
    "PyxDI",
    "dep",
    "request",
    "singleton",
    "transient",
]
