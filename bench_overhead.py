"""Benchmark AnyDI overhead compared to plain function calls."""

from __future__ import annotations

import time
from typing import Callable, Literal

from anydi import Container

ScopeMode = Literal["singleton", "transient", "request"]
SYNC_ITERATIONS = 100_000


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


def _build_plain_graph() -> Application:
    config = Config()
    repository = Repository(config)
    service = Service(repository)
    use_case = UseCase(service)
    controller = Controller(use_case)
    handler = Handler(controller)
    middleware = Middleware(handler)
    gateway = Gateway(middleware)
    facade = Facade(gateway)
    return Application(facade)


def _make_anydi_workload(container: Container, scope: ScopeMode) -> Callable[[], str]:
    if scope == "request":

        def workload() -> str:
            with container.request_context():
                return container.resolve(Application).start()

        return workload

    def workload() -> str:
        return container.resolve(Application).start()

    return workload


def _make_plain_workload(scope: ScopeMode) -> Callable[[], str]:
    if scope == "singleton":
        app = _build_plain_graph()

        def workload() -> str:
            return app.start()

        return workload

    def workload() -> str:
        return _build_plain_graph().start()

    return workload


def _measure(workload: Callable[[], str], iterations: int) -> float:
    start = time.perf_counter()
    for _ in range(iterations):
        result = workload()
        assert result == "hello world"
    return (time.perf_counter() - start) / iterations


def benchmark_scope(scope: ScopeMode, iterations: int = SYNC_ITERATIONS) -> tuple[float, float]:
    container = _build_container(scope)
    workload_anydi = _make_anydi_workload(container, scope)
    workload_plain = _make_plain_workload(scope)
    try:
        plain = _measure(workload_plain, iterations)
        anydi = _measure(workload_anydi, iterations)
    finally:
        container.close()
    return plain, anydi


def run(iterations: int = SYNC_ITERATIONS) -> None:
    for scope in ("singleton", "transient", "request"):
        plain, anydi_time = benchmark_scope(scope, iterations)
        overhead = anydi_time - plain
        ratio = anydi_time / plain if plain else float("inf")
        print(
            f"[sync][{scope}] plain={plain * 1e6:.2f}µs | "
            f"anydi={anydi_time * 1e6:.2f}µs | overhead={overhead * 1e6:.2f}µs | "
            f"ratio={ratio:.2f}x"
        )


if __name__ == "__main__":  # pragma: no cover
    print(f"Running overhead benchmarks ({SYNC_ITERATIONS} iterations)...")
    run()
