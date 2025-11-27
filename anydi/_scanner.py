from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Any

from ._decorators import Provided, is_injectable, is_provided

if TYPE_CHECKING:
    from ._container import Container

Package = ModuleType | str
PackageOrIterable = Package | Iterable[Package]


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
            packages = [packages]

        tags_list = list(tags) if tags else []
        provided_classes: list[type[Provided]] = []
        injectable_dependencies: list[ScannedDependency] = []

        # Single pass: collect both @provided classes and @injectable functions
        for module in self._iter_modules(packages):
            provided_classes.extend(self._scan_module_for_provided(module))
            injectable_dependencies.extend(
                self._scan_module_for_injectable(module, tags=tags_list)
            )

        # First: register @provided classes
        for cls in provided_classes:
            if not self._container.is_registered(cls):
                scope = cls.__provided__["scope"]
                self._container.register(cls, scope=scope)

        # Second: inject @injectable functions
        for dependency in injectable_dependencies:
            decorated = self._container.inject()(dependency.member)
            setattr(dependency.module, dependency.member.__name__, decorated)

    def _iter_modules(self, packages: Iterable[Package]) -> Iterator[ModuleType]:
        """Iterate over all modules in the given packages."""
        for package in packages:
            if isinstance(package, str):
                package = importlib.import_module(package)

            # Single module (not a package)
            if not hasattr(package, "__path__"):
                yield package
                continue

            # Package - walk all submodules
            for module_info in pkgutil.walk_packages(
                package.__path__, prefix=package.__name__ + "."
            ):
                yield importlib.import_module(module_info.name)

    def _scan_module_for_provided(self, module: ModuleType) -> list[type[Provided]]:
        """Scan a module for @provided classes."""
        provided_classes: list[type[Provided]] = []

        for _, member in inspect.getmembers(module, predicate=inspect.isclass):
            if getattr(member, "__module__", None) != module.__name__:
                continue

            if is_provided(member):
                provided_classes.append(member)

        return provided_classes

    def _scan_module_for_injectable(
        self, module: ModuleType, *, tags: list[str]
    ) -> list[ScannedDependency]:
        """Scan a module for @injectable functions."""
        dependencies: list[ScannedDependency] = []

        for _, member in inspect.getmembers(module, predicate=callable):
            if getattr(member, "__module__", None) != module.__name__:
                continue

            if self._should_include_member(member, tags=tags):
                dependencies.append(ScannedDependency(member=member, module=module))

        return dependencies

    @staticmethod
    def _should_include_member(member: Callable[..., Any], *, tags: list[str]) -> bool:
        """Determine if a member should be included based on tags or marker defaults."""
        if is_injectable(member):
            member_tags = set(member.__injectable__["tags"] or [])
            if tags:
                return bool(set(tags) & member_tags)
            return True  # No tags passed → include all injectables

        return False
