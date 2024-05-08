from __future__ import annotations

import pytest
from typing_extensions import Annotated

from anydi import Container


@pytest.fixture
def container() -> Container:
    return Container()


def test_future_annotation(container: Container) -> None:
    @container.provider(scope="singleton")
    def dep() -> Annotated[int, "dep"]:
        return 123

    assert container.resolve(Annotated[int, "dep"]) == 123
