from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Iterable
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Union

from ._decorators import is_injectable
from ._typing import get_typed_parameters, is_inject_marker

if TYPE_CHECKING:
    from ._container import Container

Package = Union[ModuleType, str]
PackageOrIterable = Union[Package, Iterable[Package]]


@dataclass(kw_only=True)
class ScannedDependency:
    member: Any
    module: ModuleType

    def __post_init__(self) -> None:
        # Unwrap decorated functions if necessary
        if hasattr(self.member, "__wrapped__"):
            self.member = self.member.__wrapped__


class Scanner:
    def __init__(self, container: Container) -> None:
        self._container = container

    def scan(
        self, /, packages: PackageOrIterable, *, tags: Iterable[str] | None = None
    ) -> None:
        """Scan packages or modules for decorated members and inject dependencies."""
        if isinstance(packages, (ModuleType, str)):
            scan_packages: Iterable[Package] = [packages]
        else:
            scan_packages = packages

        dependencies = [
            dependency
            for package in scan_packages
            for dependency in self._scan_package(package, tags=tags)
        ]

        for dependency in dependencies:
            decorated = self._container.inject()(dependency.member)
            setattr(dependency.module, dependency.member.__name__, decorated)

    def _scan_package(
        self, package: Package, *, tags: Iterable[str] | None = None
    ) -> list[ScannedDependency]:
        """Scan a package or module for decorated members."""
        tags = list(tags) if tags else []

        if isinstance(package, str):
            package = importlib.import_module(package)

        if not hasattr(package, "__path__"):
            return self._scan_module(package, tags=tags)

        dependencies: list[ScannedDependency] = []
        for module_info in pkgutil.walk_packages(
            package.__path__, prefix=package.__name__ + "."
        ):
            module = importlib.import_module(module_info.name)
            dependencies.extend(self._scan_module(module, tags=tags))

        return dependencies

    def _scan_module(
        self, module: ModuleType, *, tags: Iterable[str]
    ) -> list[ScannedDependency]:
        """Scan a module for decorated members."""
        dependencies: list[ScannedDependency] = []

        for _, member in inspect.getmembers(module, predicate=callable):
            if getattr(member, "__module__", None) != module.__name__:
                continue

            if self._should_include_member(member, tags=tags):
                dependencies.append(ScannedDependency(member=member, module=module))

        return dependencies

    @staticmethod
    def _should_include_member(
        member: Callable[..., Any], *, tags: Iterable[str]
    ) -> bool:
        """Determine if a member should be included based on tags or marker defaults."""

        if is_injectable(member):
            member_tags = set(member.__injectable__["tags"] or [])
            if tags:
                return bool(set(tags) & member_tags)
            return True  # No tags passed → include all injectables

        # If no tags are passed and not explicitly injectable,
        # check for parameter markers
        if not tags:
            for param in get_typed_parameters(member):
                if is_inject_marker(param.default):
                    return True

        return False
