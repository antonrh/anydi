import pytest

from anydi import Container
from anydi.ext import pytest_plugin


class Service:
    pass


class UnknownService:
    pass


@pytest.fixture(scope="module")
def container() -> Container:
    container = Container()
    container.register(Service, lambda: Service(), scope="singleton")
    return container


def test_anydi_inject_all_default(request: pytest.FixtureRequest) -> None:
    assert request.config.getini("anydi_inject_all") is False


def test_no_container_setup(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pytest_plugin, "CONTAINER_FIXTURE_NAME", "container1")

    with pytest.raises(pytest.FixtureLookupError) as exc_info:
        request.getfixturevalue("anydi_setup_container")

    assert exc_info.value.msg == (
        "`container` fixture is not found. Make sure to define it in your test module "
        "or override `anydi_setup_container` fixture."
    )


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
