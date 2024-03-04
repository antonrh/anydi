from typing import Any, List

import pytest

from anydi import Container


class Service:
    pass


class UnknownService:
    pass


@pytest.fixture
def container() -> Container:
    container = Container(strict=True)
    container.register(Service, lambda: Service(), scope="singleton")
    return container


def test_anydi_inject_all_default(request: pytest.FixtureRequest) -> None:
    assert request.config.getini("anydi_inject_all") is False


@pytest.fixture(autouse=True)
def _clean_unresolved(_anydi_unresolved: List[Any]) -> None:
    _anydi_unresolved.clear()


@pytest.mark.inject
def test_inject_service(service: Service) -> None:
    assert isinstance(service, Service)


@pytest.mark.xfail
@pytest.mark.inject
def test_inject_unknown_service(unknown_service: UnknownService) -> None:
    pass


@pytest.mark.inject
async def test_ainject_service(service: Service) -> None:
    assert isinstance(service, Service)


@pytest.mark.xfail
@pytest.mark.inject
async def test_ainject_unknown_service(unknown_service: UnknownService) -> None:
    pass


@pytest.mark.xfail
@pytest.mark.inject
def test_inject_missing_type(service) -> None:  # type: ignore[no-untyped-def]
    pass
