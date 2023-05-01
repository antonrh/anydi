import typing as t

import pytest

from pyxdi.utils import get_full_qualname, is_builtin_type

from tests.fixtures import Service


@pytest.mark.parametrize(
    "obj, expected",
    [
        (str, "str"),
        (Service, "tests.fixtures.Service"),
        ("test", "__main__.unknown[str]"),
    ],
)
def test_get_full_qualname(obj: t.Any, expected: str) -> None:
    name = get_full_qualname(obj)

    assert name == expected


@pytest.mark.parametrize(
    "tp, expected",
    [
        (bool, True),
        (str, True),
        (int, True),
        (float, True),
        (Service, False),
    ],
)
def test_is_builtin_type(tp: t.Type[t.Any], expected: bool) -> None:
    assert is_builtin_type(tp) == expected
