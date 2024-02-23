from typing_extensions import Literal

Scope = Literal["transient", "singleton", "request"]


class DependencyMark:
    """A marker class used to represent a dependency mark."""

    __slots__ = ()
