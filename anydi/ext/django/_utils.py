from collections.abc import Iterator

from django.urls import URLPattern, URLResolver


def iter_urlpatterns(
    urlpatterns: list[URLPattern | URLResolver],
) -> Iterator[URLPattern]:
    """Iterate over all views in urlpatterns."""
    for url_pattern in urlpatterns:
        if isinstance(url_pattern, URLResolver):
            yield from iter_urlpatterns(url_pattern.url_patterns)
        else:
            yield url_pattern
