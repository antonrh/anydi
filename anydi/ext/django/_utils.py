from __future__ import annotations

from collections.abc import Iterator
from functools import wraps
from typing import Any

from django.conf import settings
from django.core.cache import BaseCache, caches
from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper
from django.urls import URLPattern, URLResolver, get_resolver
from typing_extensions import Annotated, get_origin

from anydi import Container


def register_settings(
    container: Container, prefix: str = "django.conf.settings."
) -> None:
    """Register Django settings into the container."""

    # Ensure prefix ends with a dot
    if prefix[-1] != ".":
        prefix += "."

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
    _patch_any_typed_annotated(container, prefix=prefix)


def register_components(container: Container) -> None:
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


def inject_urlpatterns(container: Container, *, urlconf: str) -> None:
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


def _get_setting_value(value: Any) -> Any:
    return lambda: value


def _any_typed_interface(interface: Any, prefix: str) -> Any:
    origin = get_origin(interface)
    if origin is not Annotated:
        return interface  # pragma: no cover
    named = interface.__metadata__[-1]

    if isinstance(named, str) and named.startswith(prefix):
        _, setting_name = named.rsplit(prefix, maxsplit=1)
        return Annotated[Any, f"{prefix}{setting_name}"]
    return interface


def _patch_any_typed_annotated(container: Container, *, prefix: str) -> None:
    def _patch_resolve(resolve: Any) -> Any:
        @wraps(resolve)
        def wrapper(interface: Any) -> Any:
            return resolve(_any_typed_interface(interface, prefix))

        return wrapper

    def _patch_aresolve(resolve: Any) -> Any:
        @wraps(resolve)
        async def wrapper(interface: Any) -> Any:
            return await resolve(_any_typed_interface(interface, prefix))

        return wrapper

    container.resolve = _patch_resolve(  # type: ignore[method-assign]
        container.resolve
    )
    container.aresolve = _patch_aresolve(  # type: ignore[method-assign]
        container.aresolve
    )
