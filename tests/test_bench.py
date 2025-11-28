from __future__ import annotations

from collections.abc import Awaitable, Callable
from statistics import fmean
from time import perf_counter

import pytest

from anydi import Container, Scope

SYNC_ITERATIONS = 100000
SYNC_THRESHOLDS: dict[Scope, float] = {
    "singleton": 0.06,
    "transient": 0.3,
    "request": 0.7,
}

ASYNC_ITERATIONS = 100000
ASYNC_THRESHOLDS: dict[Scope, float] = {
    "singleton": 0.08,
    "transient": 0.45,
    "request": 0.85,
}


class Config:
    __slots__ = ("ready",)

    def __init__(self) -> None:
        self.ready = True


class Repository:
    def __init__(self, config: Config) -> None:
        self._config = config

    def read(self) -> bool:
        return self._config.ready


class Service:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    def handle(self) -> bool:
        return self._repository.read()


class UseCase:
    def __init__(self, service: Service) -> None:
        self._service = service

    def execute(self) -> bool:
        return self._service.handle()


class Controller:
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    def run(self) -> bool:
        return self._use_case.execute()


class Handler:
    def __init__(self, controller: Controller) -> None:
        self._controller = controller

    def handle(self) -> bool:
        return self._controller.run()


class Middleware:
    def __init__(self, handler: Handler) -> None:
        self._handler = handler

    def process(self) -> bool:
        return self._handler.handle()


class Gateway:
    def __init__(self, middleware: Middleware) -> None:
        self._middleware = middleware

    def execute(self) -> bool:
        return self._middleware.process()


class Facade:
    def __init__(self, gateway: Gateway) -> None:
        self._gateway = gateway

    def run(self) -> bool:
        return self._gateway.execute()


class Application:
    def __init__(self, facade: Facade) -> None:
        self._facade = facade

    def start(self) -> bool:
        return self._facade.run()


def make_container(scope: Scope) -> Container:  # noqa: C901
    container = Container()

    @container.provider(scope=scope)
    def provide_config() -> Config:
        return Config()

    @container.provider(scope=scope)
    def provide_repository(config: Config) -> Repository:
        return Repository(config)

    @container.provider(scope=scope)
    def provide_service(repository: Repository) -> Service:
        return Service(repository)

    @container.provider(scope=scope)
    def provide_use_case(service: Service) -> UseCase:
        return UseCase(service)

    @container.provider(scope=scope)
    def provide_controller(use_case: UseCase) -> Controller:
        return Controller(use_case)

    @container.provider(scope=scope)
    def provide_handler(controller: Controller) -> Handler:
        return Handler(controller)

    @container.provider(scope=scope)
    def provide_middleware(handler: Handler) -> Middleware:
        return Middleware(handler)

    @container.provider(scope=scope)
    def provide_gateway(middleware: Middleware) -> Gateway:
        return Gateway(middleware)

    @container.provider(scope=scope)
    def provide_facade(gateway: Gateway) -> Facade:
        return Facade(gateway)

    @container.provider(scope=scope)
    def provide_application(facade: Facade) -> Application:
        return Application(facade)

    return container


def make_sync_workload(container: Container, scope: Scope) -> Callable[[], bool]:
    if scope == "request":

        def workload() -> bool:
            with container.request_context():
                return container.resolve(Application).start()

        return workload

    def workload() -> bool:
        return container.resolve(Application).start()

    return workload


def make_async_workload(
    container: Container, scope: Scope
) -> Callable[[], Awaitable[bool]]:
    if scope == "request":

        async def workload() -> bool:
            async with container.arequest_context():
                return (await container.aresolve(Application)).start()

        return workload

    async def workload() -> bool:
        return (await container.aresolve(Application)).start()

    return workload


def assert_threshold(
    total_duration: float, thresholds: dict[Scope, float], scope: Scope, mode: str
) -> None:
    limit = thresholds[scope]
    assert total_duration < limit, (
        f"[{mode}][{scope}] regression: {total_duration:.6f}s >= {limit:.6f}s"
    )


def run_benchmark(
    workload: Callable[[], bool], *, iterations: int, rounds: int = 1
) -> float:
    durations: list[float] = []
    for _ in range(rounds):
        start = perf_counter()
        for _ in range(iterations):
            workload()
        durations.append(perf_counter() - start)
    return fmean(durations)


async def run_benchmark_async(
    workload: Callable[[], Awaitable[bool]], *, iterations: int, rounds: int = 1
) -> float:
    durations: list[float] = []
    for _ in range(rounds):
        start = perf_counter()
        for _ in range(iterations):
            await workload()
        durations.append(perf_counter() - start)
    return fmean(durations)


@pytest.mark.parametrize("scope", ["singleton", "transient", "request"])
def test_benchmark_sync(scope: Scope) -> None:
    container = make_container(scope)
    workload = make_sync_workload(container, scope)

    total_duration = run_benchmark(
        workload,
        iterations=SYNC_ITERATIONS,
    )

    assert_threshold(
        total_duration,
        SYNC_THRESHOLDS,
        scope,
        "sync",
    )


@pytest.mark.parametrize("scope", ["singleton", "transient", "request"])
async def test_benchmark_async(scope: Scope) -> None:
    container = make_container(scope)
    workload = make_async_workload(container, scope)

    total_duration = await run_benchmark_async(
        workload,
        iterations=ASYNC_ITERATIONS,
    )

    assert_threshold(
        total_duration,
        ASYNC_THRESHOLDS,
        scope,
        "async",
    )
