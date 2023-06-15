import typing as t

import pytest

from pyxdi.utils import get_full_qualname

from tests.fixtures import Service


@pytest.mark.parametrize(
    "obj, expected_qualname",
    [
        (int, "int"),
        (Service, "tests.fixtures.Service"),
        (Service(ident="test"), "tests.fixtures.Service"),
        (lambda x: x, "tests.test_utils.<lambda>"),
        (123, "int"),
        ("hello", "str"),
    ],
)
def test_get_full_qualname(obj: t.Any, expected_qualname: str) -> None:
    qualname = get_full_qualname(obj)

    assert qualname == expected_qualname
