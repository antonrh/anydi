from typing import cast

from django.apps.registry import apps
from django.utils.functional import SimpleLazyObject

import anydi

from .apps import ContainerConfig

__all__ = ["container"]


def _get_container() -> anydi.Container:
    app_config = cast(ContainerConfig, apps.get_app_config(ContainerConfig.label))
    return app_config.container


container = cast(anydi.Container, SimpleLazyObject(_get_container))
