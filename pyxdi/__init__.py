import warnings

from initdi import (
    InitDI as PyxDI,
    Module,
    Named,
    Provider,
    Scope,
    dep,
    inject,
    provider,
    request,
    singleton,
    transient,
)

__all__ = [
    "dep",
    "inject",
    "Module",
    "Named",
    "provider",
    "Provider",
    "PyxDI",
    "Scope",
    "singleton",
    "request",
    "transient",
]


warnings.warn(
    (
        "The `pyxdi` package is deprecated and will be removed in version 0.20.0. "
        "Please use the `initdi` package instead."
    ),
    DeprecationWarning,
    stacklevel=2,
)
