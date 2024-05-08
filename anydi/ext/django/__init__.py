from ._container import container
from ._utils import inject_urlpatterns, register_components, register_settings

__all__ = [
    "container",
    "register_components",
    "register_settings",
    "inject_urlpatterns",
]
