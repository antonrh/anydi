import typing as t

import pytest
from typing_extensions import Annotated

from anydi._utils import get_full_qualname, is_builtin_type

from tests.fixtures import Service


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


@pytest.mark.parametrize(
    "obj, expected_qualname",
    [
        (int, "int"),
        (Service, "tests.fixtures.Service"),
        (Service(ident="test"), "tests.fixtures.Service"),
        (
            Annotated[Service, "service"],
            'typing.Annotated[tests.fixtures.Service, "service"]',
        ),
        (lambda x: x, "tests.test_utils.<lambda>"),
        (123, "int"),
        ("hello", "str"),
        (str | int, "types.UnionType[str, int]"),
    ],
)
def test_get_full_qualname(obj: t.Any, expected_qualname: str) -> None:
    qualname = get_full_qualname(obj)

    assert qualname == expected_qualname
