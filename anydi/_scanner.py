from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Iterable
from dataclasses import dataclass
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    TypeVar,
    Union,
    cast,
    final,
    overload,
)

from typing_extensions import NamedTuple, ParamSpec

from ._types import is_marker
from ._utils import get_typed_parameters

if TYPE_CHECKING:
    from ._container import Container


T = TypeVar("T")
P = ParamSpec("P")


@dataclass(frozen=True)
class Dependency:
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
        packages: ModuleType | str | Iterable[ModuleType | str],
        *,
        tags: Iterable[str] | None = None,
    ) -> None:
        """Scan packages or modules for decorated members and inject dependencies."""
        dependencies: list[Dependency] = []

        if isinstance(packages, Iterable) and not isinstance(packages, str):
            scan_packages: Iterable[ModuleType | str] = packages
        else:
            scan_packages = cast(Iterable[Union[ModuleType, str]], [packages])

        for package in scan_packages:
            dependencies.extend(self._scan_package(package, tags=tags))

        for dependency in dependencies:
            decorator = self.container.inject()(dependency.member)
            setattr(dependency.module, dependency.member.__name__, decorator)

    def _scan_package(
        self,
        package: ModuleType | str,
        *,
        tags: Iterable[str] | None = None,
    ) -> list[Dependency]:
        """Scan a package or module for decorated members."""
        tags = tags or []
        if isinstance(package, str):
            package = importlib.import_module(package)

        package_path = getattr(package, "__path__", None)

        if not package_path:
            return self._scan_module(package, tags=tags)

        dependencies: list[Dependency] = []

        for module_info in pkgutil.walk_packages(
            path=package_path, prefix=package.__name__ + "."
        ):
            module = importlib.import_module(module_info.name)
            dependencies.extend(self._scan_module(module, tags=tags))

        return dependencies

    def _scan_module(
        self, module: ModuleType, *, tags: Iterable[str]
    ) -> list[Dependency]:
        """Scan a module for decorated members."""
        dependencies: list[Dependency] = []

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
                parameters = get_typed_parameters(member.__init__)
            else:
                parameters = get_typed_parameters(member)
            for parameter in parameters:
                if is_marker(parameter.default):
                    dependencies.append(
                        self._create_dependency(member=member, module=module)
                    )
                    continue

        return dependencies

    def _create_dependency(self, member: Any, module: ModuleType) -> Dependency:
        """Create a `Dependency` object from the scanned member and module."""
        if hasattr(member, "__wrapped__"):
            member = member.__wrapped__
        return Dependency(member=member, module=module)


class InjectDecoratorArgs(NamedTuple):
    wrapped: bool
    tags: Iterable[str] | None


@overload
def injectable(func: Callable[P, T]) -> Callable[P, T]: ...


@overload
def injectable(
    *, tags: Iterable[str] | None = None
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


def injectable(
    func: Callable[P, T] | None = None,
    tags: Iterable[str] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]] | Callable[P, T]:
    """Decorator for marking a function or method as requiring dependency injection."""

    def decorator(inner: Callable[P, T]) -> Callable[P, T]:
        setattr(inner, "__injectable__", InjectDecoratorArgs(wrapped=True, tags=tags))
        return inner

    if func is None:
        return decorator

    return decorator(func)
