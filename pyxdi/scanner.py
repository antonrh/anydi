from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Union, cast

from typing_extensions import final

from .types import DependencyMark
from .utils import get_signature

if TYPE_CHECKING:
    from .core import PyxDI


class ScannedDependency:
    """Represents a scanned dependency.

    Attributes:
        member: The member object that represents the dependency.
        module: The module where the dependency is defined.
    """

    __slots__ = ("member", "module")

    def __init__(self, member: Any, module: ModuleType) -> None:
        self.member = member
        self.module = module


@final
class DependencyScanner:
    """A class for scanning packages or modules for decorated objects
    and injecting dependencies."""

    def __init__(self, root: PyxDI) -> None:
        self.root = root

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
        dependencies: List[ScannedDependency] = []

        if isinstance(packages, Iterable) and not isinstance(packages, str):
            scan_packages: Iterable[Union[ModuleType, str]] = packages
        else:
            scan_packages = cast(Iterable[Union[ModuleType, str]], [packages])

        for package in scan_packages:
            dependencies.extend(self._scan_package(package, tags=tags))

        for dependency in dependencies:
            decorator = self.root.inject()(dependency.member)
            setattr(dependency.module, dependency.member.__name__, decorator)

    def _scan_package(
        self,
        package: Union[ModuleType, str],
        *,
        tags: Optional[Iterable[str]] = None,
    ) -> List[ScannedDependency]:
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

        dependencies: List[ScannedDependency] = []

        for module_info in pkgutil.walk_packages(
            path=package_path, prefix=package.__name__ + "."
        ):
            module = importlib.import_module(module_info.name)
            dependencies.extend(self._scan_module(module, tags=tags))

        return dependencies

    def _scan_module(
        self, module: ModuleType, *, tags: Iterable[str]
    ) -> List[ScannedDependency]:
        """Scan a module for decorated members.

        Args:
            module: The module to scan.
            tags: List of tags to filter the scanned members. Only members with at
                least one matching tag will be scanned.

        Returns:
            A list of scanned dependencies.
        """
        dependencies: List[ScannedDependency] = []

        for _, member in inspect.getmembers(module):
            if getattr(member, "__module__", None) != module.__name__ or not callable(
                member
            ):
                continue

            member_tags = getattr(member, "__pyxdi_tags__", [])
            if tags and (
                member_tags
                and not set(member_tags).intersection(tags)
                or not member_tags
            ):
                continue

            injected = getattr(member, "__pyxdi_inject__", None)
            if injected:
                dependencies.append(
                    self._create_scanned_dependency(member=member, module=module)
                )
                continue

            # Get by pyxdi.dep mark
            if inspect.isclass(member):
                signature = get_signature(member.__init__)
            else:
                signature = get_signature(member)
            for parameter in signature.parameters.values():
                if isinstance(parameter.default, DependencyMark):
                    dependencies.append(
                        self._create_scanned_dependency(member=member, module=module)
                    )
                    continue

        return dependencies

    def _create_scanned_dependency(
        self, member: Any, module: ModuleType
    ) -> ScannedDependency:
        """Create a `ScannedDependency` object from the scanned member and module.

        Args:
            member: The scanned member.
            module: The module containing the scanned member.

        Returns:
            A `ScannedDependency` object.
        """
        if hasattr(member, "__wrapped__"):
            member = member.__wrapped__
        return ScannedDependency(member=member, module=module)
