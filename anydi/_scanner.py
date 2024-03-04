from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
    final,
    overload,
)

from typing_extensions import NamedTuple, ParamSpec

from ._types import Marker
from ._utils import get_signature

if TYPE_CHECKING:
    from ._container import Container


T = TypeVar("T")
P = ParamSpec("P")


@dataclass(frozen=True)
class Dependency:
    """Represents a scanned dependency.

    Attributes:
        member: The member object that represents the dependency.
        module: The module where the dependency is defined.
    """

    member: Any
    module: ModuleType


@final
class Scanner:
    """A class for scanning packages or modules for decorated objects
    and injecting dependencies."""

    def __init__(self, container: Container) -> None:
        self.container = container

    def scan(
        self,
        /,
        packages: Union[Union[ModuleType, str], Iterable[Union[ModuleType, str]]],
        *,
        tags: Optional[Iterable[str]] = None,
    ) -> None:
        """Scan packages or modules for decorated members and inject dependencies.

        Args:
            packages: A single package or module to scan,
                or an iterable of packages or modules to scan.
            tags: Optional list of tags to filter the scanned members. Only members
                with at least one matching tag will be scanned. Defaults to None.
        """
        dependencies: List[Dependency] = []

        if isinstance(packages, Iterable) and not isinstance(packages, str):
            scan_packages: Iterable[Union[ModuleType, str]] = packages
        else:
            scan_packages = cast(Iterable[Union[ModuleType, str]], [packages])

        for package in scan_packages:
            dependencies.extend(self._scan_package(package, tags=tags))

        for dependency in dependencies:
            decorator = self.container.inject()(dependency.member)
            setattr(dependency.module, dependency.member.__name__, decorator)

    def _scan_package(
        self,
        package: Union[ModuleType, str],
        *,
        tags: Optional[Iterable[str]] = None,
    ) -> List[Dependency]:
        """Scan a package or module for decorated members.

        Args:
            package: The package or module to scan.
            tags: Optional list of tags to filter the scanned members. Only members
                with at least one matching tag will be scanned. Defaults to None.

        Returns:
            A list of scanned dependencies.
        """
        tags = tags or []
        if isinstance(package, str):
            package = importlib.import_module(package)

        package_path = getattr(package, "__path__", None)

        if not package_path:
            return self._scan_module(package, tags=tags)

        dependencies: List[Dependency] = []

        for module_info in pkgutil.walk_packages(
            path=package_path, prefix=package.__name__ + "."
        ):
            module = importlib.import_module(module_info.name)
            dependencies.extend(self._scan_module(module, tags=tags))

        return dependencies

    def _scan_module(
        self, module: ModuleType, *, tags: Iterable[str]
    ) -> List[Dependency]:
        """Scan a module for decorated members.

        Args:
            module: The module to scan.
            tags: List of tags to filter the scanned members. Only members with at
                least one matching tag will be scanned.

        Returns:
            A list of scanned dependencies.
        """
        dependencies: List[Dependency] = []

        for _, member in inspect.getmembers(module):
            if getattr(member, "__module__", None) != module.__name__ or not callable(
                member
            ):
                continue

            decorator_args: InjectDecoratorArgs = getattr(
                member,
                "__injectable__",
                InjectDecoratorArgs(wrapped=False, tags=[]),
            )

            if tags and (
                decorator_args.tags
                and not set(decorator_args.tags).intersection(tags)
                or not decorator_args.tags
            ):
                continue

            if decorator_args.wrapped:
                dependencies.append(
                    self._create_dependency(member=member, module=module)
                )
                continue

            # Get by Marker
            if inspect.isclass(member):
                signature = get_signature(member.__init__)
            else:
                signature = get_signature(member)
            for parameter in signature.parameters.values():
                if isinstance(parameter.default, Marker):
                    dependencies.append(
                        self._create_dependency(member=member, module=module)
                    )
                    continue

        return dependencies

    def _create_dependency(self, member: Any, module: ModuleType) -> Dependency:
        """Create a `Dependency` object from the scanned member and module.

        Args:
            member: The scanned member.
            module: The module containing the scanned member.

        Returns:
            A `ScannedDependency` object.
        """
        if hasattr(member, "__wrapped__"):
            member = member.__wrapped__
        return Dependency(member=member, module=module)


class InjectDecoratorArgs(NamedTuple):
    wrapped: bool
    tags: Optional[Iterable[str]]


@overload
def injectable(obj: Callable[P, T]) -> Callable[P, T]: ...


@overload
def injectable(
    *, tags: Optional[Iterable[str]] = None
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


def injectable(
    obj: Optional[Callable[P, T]] = None,
    tags: Optional[Iterable[str]] = None,
) -> Union[
    Callable[
        [Callable[P, T]],
        Callable[P, T],
    ],
    Callable[P, T],
]:
    """Decorator for marking a function or method as requiring dependency injection.

    Args:
        obj: The target function or method to be decorated.
        tags: Optional tags to associate with the injection point.

    Returns:
        If `obj` is provided, returns the decorated target function or method.
        If `obj` is not provided, returns a decorator that can be used to mark
        a function or method as requiring dependency injection.
    """

    def decorator(obj: Callable[P, T]) -> Callable[P, T]:
        setattr(obj, "__injectable__", InjectDecoratorArgs(wrapped=True, tags=tags))
        return obj

    if obj is None:
        return decorator

    return decorator(obj)
