from __future__ import annotations

import logging
import types
from typing import Callable, cast

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

import anydi

from ._settings import get_settings
from ._utils import inject_urlpatterns, register_components, register_settings

logger = logging.getLogger(__name__)


class ContainerConfig(AppConfig):  # type: ignore[misc]
    name = "anydi.ext.django"
    label = "anydi_django"

    def __init__(self, app_name: str, app_module: types.ModuleType | None) -> None:
        super().__init__(app_name, app_module)
        self.settings = get_settings()
        # Create a container
        container_factory_path = self.settings["CONTAINER_FACTORY"]
        if container_factory_path:
            try:
                container_factory = cast(
                    Callable[[], anydi.Container], import_string(container_factory_path)
                )
            except ImportError as exc:
                raise ImproperlyConfigured(
                    f"Cannot import container factory '{container_factory_path}'."
                ) from exc
            self.container = container_factory()
        else:
            self.container = anydi.Container(
                strict=self.settings["STRICT_MODE"],
            )

    def ready(self) -> None:  # noqa: C901
        # Register Django settings
        if self.settings["REGISTER_SETTINGS"]:
            register_settings(
                self.container,
                prefix=getattr(
                    settings,
                    "ANYDI_SETTINGS_PREFIX",
                    "django.conf.settings.",
                ),
            )

        # Register Django components
        if self.settings["REGISTER_COMPONENTS"]:
            register_components(self.container)

        # Register modules
        for module_path in self.settings["MODULES"]:
            try:
                module_cls = import_string(module_path)
            except ImportError as exc:
                raise ImproperlyConfigured(
                    f"Cannot import module '{module_path}'."
                ) from exc
            self.container.register_module(module_cls)

        # Patching the django-ninja framework if it installed
        if self.settings["PATCH_NINJA"]:
            from .ninja import patch_ninja

            patch_ninja()

        # Auto-injecting the container into views
        if urlconf := self.settings["INJECT_URLCONF"]:
            inject_urlpatterns(self.container, urlconf=urlconf)

        # Scan packages
        for scan_package in self.settings["SCAN_PACKAGES"]:
            self.container.scan(scan_package)
