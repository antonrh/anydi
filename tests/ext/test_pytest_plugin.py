import pytest


def test_anydi_inject_all_default(request: pytest.FixtureRequest) -> None:
    assert request.config.getini("anydi_inject_all") is False
