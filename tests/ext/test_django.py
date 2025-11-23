import pytest


def test_django_extension_requires_extra() -> None:
    with pytest.raises(ImportError, match="anydi_django"):
        __import__("anydi.ext.django")
