import sys
from typing import Annotated, Any, Union

import pytest

from anydi import Container
from anydi._utils import get_full_qualname, import_string, is_builtin_type

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
def test_is_builtin_type(tp: type[Any], expected: bool) -> None:
    assert is_builtin_type(tp) == expected


@pytest.mark.parametrize(
    "obj, expected_qualname",
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
        ("hello", "str"),
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
def test_get_full_qualname(obj: Any, expected_qualname: str) -> None:
    qualname = get_full_qualname(obj)

    assert qualname == expected_qualname


def test_import_string() -> None:
    assert import_string("anydi.Container") is Container


def test_import_string_invalid_path() -> None:
    with pytest.raises(ImportError):
        import_string("anydi.InvalidClass")
