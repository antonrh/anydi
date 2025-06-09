from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Iterable
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Any, Union

from ._decorators import InjectableMetadata
from ._utils import get_typed_parameters, is_marker

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

    @staticmethod
    def _scan_module(
        module: ModuleType, *, tags: Iterable[str]
    ) -> list[ScannedDependency]:
        """Scan a module for decorated members."""
        dependencies: list[ScannedDependency] = []

        for _, member in inspect.getmembers(module, predicate=callable):
            if getattr(member, "__module__", None) != module.__name__:
                continue

            metadata: InjectableMetadata = getattr(
                member,
                "__injectable__",
                InjectableMetadata(wrapped=False, tags=[]),
            )

            should_include = False
            if metadata["wrapped"]:
                should_include = True
            elif tags and metadata["tags"]:
                should_include = bool(set(metadata["tags"]) & set(tags))
            elif tags and not metadata["tags"]:
                continue  # tags are provided but member has none

            if not should_include:
                for param in get_typed_parameters(member):
                    if is_marker(param.default):
                        should_include = True
                        break

            if should_include:
                dependencies.append(ScannedDependency(member=member, module=module))

        return dependencies
