import sys
from typing import Any, Type, Union

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
def test_is_builtin_type(tp: Type[Any], expected: bool) -> None:
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
        pytest.param(
            Union[str, int],
            "typing.Union[str, int]",
            marks=pytest.mark.skipif(sys.version_info < (3, 10)),
        ),
        pytest.param(
            Union[str, int],
            "typing._SpecialForm[str, int]",
            marks=pytest.mark.skipif(sys.version_info >= (3, 10)),
        ),
    ],
)
def test_get_full_qualname(obj: Any, expected_qualname: str) -> None:
    qualname = get_full_qualname(obj)

    assert qualname == expected_qualname
