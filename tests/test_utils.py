import sys
from typing import Annotated, Any, Union

import pytest

from anydi._typing import is_builtin_type, type_repr

from tests.fixtures import Service


@pytest.mark.parametrize(
    ("tp", "expected"),
    [
        (bool, True),
        (str, True),
        (int, True),
        (float, True),
        (Service, False),
    ],
)
def test_is_builtin_type(tp: type[Any], expected: bool) -> None:
    assert is_builtin_type(tp) == expected


@pytest.mark.parametrize(
    ("obj", "expected_qualname"),
    [
        (int, "int"),
        (Service, "tests.fixtures.Service"),
        (Service(ident="test"), "tests.fixtures.Service"),
        pytest.param(
            Annotated[Service, "service"],
            'Annotated[tests.fixtures.Service, "service"]',
            marks=pytest.mark.skipif(
                sys.version_info >= (3, 9), reason="Requires Python 3.9"
            ),
        ),
        (lambda x: x, "tests.test_utils.<lambda>"),
        (123, "int"),
        ("hello", "hello"),
        (list[str], "list[str]"),
        pytest.param(
            Union[str, int],
            "Union[str, int]",
            marks=pytest.mark.skipif(
                sys.version_info < (3, 10), reason="Requires Python 3.10"
            ),
        ),
        pytest.param(
            Union[str, int],
            "_SpecialForm[str, int]",
            marks=pytest.mark.skipif(
                sys.version_info >= (3, 10), reason="Requires Python 3.9"
            ),
        ),
    ],
)
def test_type_repr(obj: Any, expected_qualname: str) -> None:
    qualname = type_repr(obj)

    assert qualname == expected_qualname
