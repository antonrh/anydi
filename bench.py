"""Measure AnyDI resolve performance per scope."""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Literal

from anydi import Container

ScopeMode = Literal["singleton", "transient", "request"]
SYNC_ITERATIONS = 100000
ASYNC_ITERATIONS = 100000


class Config:
    __slots__ = ("message",)

    def __init__(self) -> None:
        self.message = "hello world"


class Repository:
    def __init__(self, config: Config) -> None:
        self._config = config

    def read(self) -> str:
        return self._config.message


class Service:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    def handle(self) -> str:
        return self._repository.read()


class UseCase:
    def __init__(self, service: Service) -> None:
        self._service = service

    def execute(self) -> str:
        return self._service.handle()


class Controller:
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    def run(self) -> str:
        return self._use_case.execute()


class Handler:
    def __init__(self, controller: Controller) -> None:
        self._controller = controller

    def handle(self) -> str:
        return self._controller.run()


class Middleware:
    def __init__(self, handler: Handler) -> None:
        self._handler = handler

    def process(self) -> str:
        return self._handler.handle()


class Gateway:
    def __init__(self, middleware: Middleware) -> None:
        self._middleware = middleware

    def execute(self) -> str:
        return self._middleware.process()


class Facade:
    def __init__(self, gateway: Gateway) -> None:
        self._gateway = gateway

    def run(self) -> str:
        return self._gateway.execute()


class Application:
    def __init__(self, facade: Facade) -> None:
        self._facade = facade

    def start(self) -> str:
        return self._facade.run()


def _build_container(scope: ScopeMode) -> Container:
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


def _make_sync_workload(container: Container, scope: ScopeMode) -> Callable[[], str]:
    if scope == "request":

        def workload() -> str:
            with container.request_context():
                return container.resolve(Application).start()

        return workload

    def workload() -> str:
        return container.resolve(Application).start()

    return workload


def _make_async_workload(
    container: Container, scope: ScopeMode
) -> Callable[[], Awaitable[str]]:
    if scope == "request":

        async def workload() -> str:
            async with container.arequest_context():
                return (await container.aresolve(Application)).start()

        return workload

    async def workload() -> str:
        return (await container.aresolve(Application)).start()

    return workload


def benchmark_sync_scope(scope: ScopeMode, iterations: int = SYNC_ITERATIONS) -> float:
    container = _build_container(scope)
    workload = _make_sync_workload(container, scope)
    start = time.perf_counter()
    for _ in range(iterations):
        result = workload()
        assert result == "hello world"
    elapsed = time.perf_counter() - start
    container.close()
    return elapsed


async def benchmark_async_scope(
    scope: ScopeMode, iterations: int = ASYNC_ITERATIONS
) -> float:
    container = _build_container(scope)
    workload = _make_async_workload(container, scope)
    start = time.perf_counter()
    for _ in range(iterations):
        result = await workload()
        assert result == "hello world"
    elapsed = time.perf_counter() - start
    await container.aclose()
    return elapsed


def run_sync(iterations: int = SYNC_ITERATIONS) -> None:
    for scope in ("singleton", "transient", "request"):
        elapsed = benchmark_sync_scope(scope, iterations)
        per_call = elapsed / iterations
        print(
            f"[sync][{scope}] total={elapsed:.6f}s | per_call={per_call * 1e6:.2f}µs"
        )


async def run_async(iterations: int = ASYNC_ITERATIONS) -> None:
    for scope in ("singleton", "transient", "request"):
        elapsed = await benchmark_async_scope(scope, iterations)
        per_call = elapsed / iterations
        print(
            f"[async][{scope}] total={elapsed:.6f}s | per_call={per_call * 1e6:.2f}µs"
        )


if __name__ == "__main__":  # pragma: no cover
    print(f"Running sync benchmarks ({SYNC_ITERATIONS} iterations)...")
    run_sync()
    print(f"\nRunning async benchmarks ({ASYNC_ITERATIONS} iterations)...")
    asyncio.run(run_async())


"""
before 1:

Running sync benchmarks (100000 iterations)...
[sync][singleton] total=0.053017s | per_call=0.53µs
[sync][transient] total=0.760905s | per_call=7.61µs
[sync][request] total=1.219930s | per_call=12.20µs

Running async benchmarks (100000 iterations)...
[async][singleton] total=1.787560s | per_call=17.88µs

before 2:

Running sync benchmarks (100000 iterations)...
[sync][singleton] total=0.047670s | per_call=0.48µs
[sync][transient] total=0.360572s | per_call=3.61µs
[sync][request] total=0.662663s | per_call=6.63µs

Running async benchmarks (100000 iterations)...
[async][singleton] total=0.067415s | per_call=0.67µs
[async][transient] total=0.548578s | per_call=5.49µs
[async][request] total=2.973560s | per_call=29.74µs

after:

Running sync benchmarks (100000 iterations)...
[sync][singleton] total=0.034488s | per_call=0.34µs
[sync][transient] total=0.194309s | per_call=1.94µs
[sync][request] total=0.436962s | per_call=4.37µs

Running async benchmarks (100000 iterations)...
[async][singleton] total=0.048808s | per_call=0.49µs
[async][transient] total=0.270550s | per_call=2.71µs
[async][request] total=0.602514s | per_call=6.03µs


--- Test container

Running sync benchmarks (100000 iterations)...
[sync][singleton] total=0.033775s | per_call=0.34µs
[sync][transient] total=0.196352s | per_call=1.96µs
[sync][request] total=0.449730s | per_call=4.50µs

Running async benchmarks (100000 iterations)...
[async][singleton] total=0.052090s | per_call=0.52µs
[async][transient] total=0.278026s | per_call=2.78µs
[async][request] total=0.603860s | per_call=6.04µs
"""
