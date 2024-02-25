import inspect
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Type, TypeVar, Union

from typing_extensions import Annotated, Literal, Mapping, TypeAlias

from ._utils import get_full_qualname, get_signature

Scope = Literal["transient", "singleton", "request"]

T = TypeVar("T")
AnyInterface: TypeAlias = Union[Type[Any], Annotated[Any, ...]]
Interface: TypeAlias = Type[T]


class Marker:
    """A marker class for marking dependencies."""

    __slots__ = ()


@dataclass(frozen=True)
class Provider:
    """Represents a provider object.

    Attributes:
        obj: The callable object that serves as the provider.
        scope: The scope of the provider.
    """

    obj: Callable[..., Any]
    scope: Scope

    def __str__(self) -> str:
        """Returns a string representation of the provider.

        Returns:
            The string representation of the provider.
        """
        return self.name

    @cached_property
    def name(self) -> str:
        """Returns the full qualified name of the provider object.

        Returns:
            The full qualified name of the provider object.
        """
        return get_full_qualname(self.obj)

    @cached_property
    def parameters(self) -> Mapping[str, inspect.Parameter]:
        """Returns the parameters of the provider as a mapping.

        Returns:
            The parameters of the provider.
        """
        return get_signature(self.obj).parameters

    @cached_property
    def is_class(self) -> bool:
        """Checks if the provider object is a class.

        Returns:
            True if the provider object is a class, False otherwise.
        """
        return inspect.isclass(self.obj)

    @cached_property
    def is_function(self) -> bool:
        """Checks if the provider object is a function.

        Returns:
            True if the provider object is a function, False otherwise.
        """
        return (inspect.isfunction(self.obj) or inspect.ismethod(self.obj)) and not (
            self.is_resource
        )

    @cached_property
    def is_coroutine(self) -> bool:
        """Checks if the provider object is a coroutine function.

        Returns:
            True if the provider object is a coroutine function, False otherwise.
        """
        return inspect.iscoroutinefunction(self.obj)

    @cached_property
    def is_generator(self) -> bool:
        """Checks if the provider object is a generator function.

        Returns:
            True if the provider object is a resource, False otherwise.
        """
        return inspect.isgeneratorfunction(self.obj)

    @cached_property
    def is_async_generator(self) -> bool:
        """Checks if the provider object is an async generator function.

        Returns:
            True if the provider object is an async resource, False otherwise.
        """
        return inspect.isasyncgenfunction(self.obj)

    @property
    def is_resource(self) -> bool:
        """Checks if the provider object is a sync or async generator function.

        Returns:
            True if the provider object is a resource, False otherwise.
        """
        return self.is_generator or self.is_async_generator
