import importlib
import pkgutil
import typing as t
from types import ModuleType


def scan_package(
    package: t.Union[ModuleType, str], include: t.Optional[t.Iterable[str]] = None
) -> None:
    if isinstance(package, str):
        package = importlib.import_module(package)
    package_path = getattr(package, "__path__", None)
    if not package_path:
        return
    include = include or [""]
    for module_info in pkgutil.walk_packages(
        path=package_path, prefix=package.__name__ + "."
    ):
        for include_name in include:
            if module_info.name.endswith(include_name):
                importlib.import_module(module_info.name)
