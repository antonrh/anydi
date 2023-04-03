import typing as t

import pytest

from pyxdi.utils import get_qualname

from tests.fixtures import Service


@pytest.mark.parametrize(
    "obj, expected",
    [
        (str, "str"),
        (Service, "tests.fixtures.Service"),
        ("test", "__main__.unknown[str]"),
    ],
)
def test_get_obj_name(obj: t.Any, expected: str) -> None:
    name = get_qualname(obj)

    assert name == expected
