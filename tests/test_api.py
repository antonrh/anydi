from unittest import mock

import pytest

import pyxdi

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
async def close_all() -> None:
    pyxdi.close()
    await pyxdi.aclose()


def test_init_in_sync_mode_already_initialized() -> None:
    pyxdi.init()

    with pytest.raises(RuntimeError) as exc_info:
        pyxdi.init()

    assert str(exc_info.value) == "`pyxdi` already initialized in `sync` mode."


def test_init_in_async_mode_already_initialized() -> None:
    pyxdi.init(mode="async")

    with pytest.raises(RuntimeError) as exc_info:
        pyxdi.init()

    assert str(exc_info.value) == "`pyxdi` already initialized in `async` mode."


def test_init_in_async_mode_anyio_not_installed() -> None:
    with pytest.raises(RuntimeError) as exc_info, mock.patch(
        "pyxdi._api.anyio_installed", new_callable=lambda: False
    ):
        pyxdi.init(mode="async")

    assert str(exc_info.value) == (
        "Please, install `async` extension run in asynchronous mode. "
        "eg. pip install pyxdi[async]."
    )


def test_init_in_sync_mode_and_close() -> None:
    pyxdi.init()

    assert pyxdi._api._di_context

    pyxdi.close()

    assert pyxdi._api._di_context is None


def test_init_with_scan_packages() -> None:
    pyxdi.init(packages=["tests.scan.a.a2"], include=["dep"])

    from tests.scan import result

    assert result == {"a", "a21", "a2", "a21:dep"}


async def test_init_in_async_mode_and_close() -> None:
    pyxdi.init(mode="async")

    assert pyxdi._api._async_di_context

    await pyxdi.aclose()

    assert pyxdi._api._async_di_context is None


def test_provider_not_initialized() -> None:
    with pytest.raises(RuntimeError) as exc_info:

        @pyxdi.provider
        def service() -> str:
            return "OK"

    assert str(exc_info.value) == (
        "`pyxdi` not initialized. Please, call `pyxdi.init()` first."
    )


def test_provider_no_arguments() -> None:
    pyxdi.init()

    @pyxdi.provider
    def service() -> str:
        return "OK"

    assert pyxdi._api._get_di_context().has_binding(str)


def test_provider_callable() -> None:
    pyxdi.init()

    @pyxdi.provider()
    def service() -> str:
        return "OK"

    assert pyxdi._api._get_di_context().has_binding(str)


def test_request_context() -> None:
    pyxdi.init()

    with pyxdi.request_context() as ctx:
        ctx.set(str, "hello")

        assert pyxdi._api._get_di_context().get(str) == "hello"


def test_request_context_not_initialized() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        with pyxdi.request_context():
            pass

    assert str(exc_info.value) == (
        '`pyxdi` not initialized. Please, call `pyxdi.init(mode="sync")` first.'
    )


async def test_arequest_context() -> None:
    pyxdi.init(mode="async")

    async with pyxdi.arequest_context() as ctx:
        ctx.set(str, "hello")

        assert (await pyxdi._api._get_async_di_context().get(str)) == "hello"


async def test_arequest_context_not_initialized() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        async with pyxdi.arequest_context():
            pass

    assert str(exc_info.value) == (
        '`pyxdi` not initialized. Please, call `pyxdi.init(mode="async")` first.'
    )


def test_inject() -> None:
    pyxdi.init()

    @pyxdi.provider()
    def message() -> str:
        return "hello"

    @pyxdi.inject
    def func(message: str = pyxdi.dep) -> str:
        return message

    result = func()

    assert result == "hello"
