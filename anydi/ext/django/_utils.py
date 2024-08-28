from collections.abc import Iterator
from typing import Any

from django.conf import settings
from django.core.cache import BaseCache, caches
from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper
from django.urls import URLPattern, URLResolver, get_resolver
from typing_extensions import Annotated

import anydi
from anydi.ext._utils import patch_any_typed_annotated


def register_settings(
    container: anydi.Container, prefix: str = "django.conf.setting."
) -> None:
    """Register Django settings into the container."""

    # Ensure prefix ends with a dot
    if prefix[-1] != ".":
        prefix += "."

    def _get_setting_value(value: Any) -> Any:
        return lambda: value

    for setting_name in dir(settings):
        setting_value = getattr(settings, setting_name)
        if not setting_name.isupper():
            continue

        container.register(
            Annotated[Any, f"{prefix}{setting_name}"],
            _get_setting_value(setting_value),
            scope="singleton",
        )

    # Patch AnyDI to resolve Any types for annotated settings
    patch_any_typed_annotated(container, prefix=prefix)


def register_components(container: anydi.Container) -> None:
    """Register Django components into the container."""

    # Register caches
    def _get_cache(cache_name: str) -> Any:
        return lambda: caches[cache_name]

    for cache_name in caches:
        container.register(
            Annotated[BaseCache, cache_name],
            _get_cache(cache_name),
            scope="singleton",
        )

    # Register database connections
    def _get_connection(alias: str) -> Any:
        return lambda: connections[alias]

    for alias in connections:
        container.register(
            Annotated[BaseDatabaseWrapper, alias],
            _get_connection(alias),
            scope="singleton",
        )


def inject_urlpatterns(container: anydi.Container, *, urlconf: str) -> None:
    """Auto-inject the container into views."""
    resolver = get_resolver(urlconf)
    for pattern in iter_urlpatterns(resolver.url_patterns):
        # Skip already injected views
        if hasattr(pattern.callback, "_injected"):
            continue
        # Skip django-ninja views
        if pattern.lookup_str.startswith("ninja."):
            continue  # pragma: no cover
        pattern.callback = container.inject(pattern.callback)
        pattern.callback._injected = True  # type: ignore[attr-defined]


def iter_urlpatterns(
    urlpatterns: list[URLPattern | URLResolver],
) -> Iterator[URLPattern]:
    """Iterate over all views in urlpatterns."""
    for url_pattern in urlpatterns:
        if isinstance(url_pattern, URLResolver):
            yield from iter_urlpatterns(url_pattern.url_patterns)
        else:
            yield url_pattern
