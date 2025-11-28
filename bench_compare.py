import importlib
import statistics
import time
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, Literal, cast
import dishka


import anydi
from anydi import Container

ITERATIONS = 100_000
REPEATS = 1
ScopeMode = Literal["singleton", "transient", "request"]


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


@dataclass(frozen=True)
class PerformanceResult:
    anydi: float
    dishka: float
    dependency_injector: float

    @staticmethod
    def _ratio(value: float, reference: float) -> float:
        if reference == 0:
            return float("inf")
        return value / reference

    @property
    def anydi_vs_dishka(self) -> float:
        return self._ratio(self.anydi, self.dishka)

    @property
    def anydi_vs_dependency_injector(self) -> float:
        return self._ratio(self.anydi, self.dependency_injector)


@dataclass(frozen=True)
class BenchmarkTarget:
    name: str
    workload: Callable[[], None]
    cleanup: Callable[[], None]


def _build_anydi_container(scope: ScopeMode, *, module: ModuleType | None = None) -> Container:
    impl = module or anydi
    container = cast(Container, impl.Container())
    auto_marker = impl.auto

    @container.provider(scope=scope)
    def provide_config() -> Config:
        return Config()

    @container.provider(scope=scope)
    def provide_repository(config: Config = auto_marker) -> Repository:
        return Repository(config)

    @container.provider(scope=scope)
    def provide_service(repository: Repository = auto_marker) -> Service:
        return Service(repository)

    @container.provider(scope=scope)
    def provide_use_case(service: Service = auto_marker) -> UseCase:
        return UseCase(service)

    @container.provider(scope=scope)
    def provide_controller(use_case: UseCase = auto_marker) -> Controller:
        return Controller(use_case)

    @container.provider(scope=scope)
    def provide_handler(controller: Controller = auto_marker) -> Handler:
        return Handler(controller)

    @container.provider(scope=scope)
    def provide_middleware(handler: Handler = auto_marker) -> Middleware:
        return Middleware(handler)

    @container.provider(scope=scope)
    def provide_gateway(middleware: Middleware = auto_marker) -> Gateway:
        return Gateway(middleware)

    @container.provider(scope=scope)
    def provide_facade(gateway: Gateway = auto_marker) -> Facade:
        return Facade(gateway)

    @container.provider(scope=scope)
    def provide_application(facade: Facade = auto_marker) -> Application:
        return Application(facade)

    return container


def _build_dishka_container(scope: ScopeMode):
    scope_mapping = {"request": dishka.Scope.REQUEST}
    provider_scope = scope_mapping.get(scope, dishka.Scope.APP)
    cache = scope != "transient"

    provider = dishka.Provider(scope=provider_scope)
    provider.provide(Config, cache=cache)
    provider.provide(Repository, cache=cache)
    provider.provide(Service, cache=cache)
    provider.provide(UseCase, cache=cache)
    provider.provide(Controller, cache=cache)
    provider.provide(Handler, cache=cache)
    provider.provide(Middleware, cache=cache)
    provider.provide(Gateway, cache=cache)
    provider.provide(Facade, cache=cache)
    provider.provide(Application, cache=cache)
    return dishka.make_container(provider)


def _make_anydi_workload(container: Container, scope: ScopeMode) -> Callable[[], None]:
    if scope == "request":
        def workload() -> None:
            with container.request_context():
                container.resolve(Application).start()

        return workload

    def workload() -> None:
        container.resolve(Application).start()

    return workload


def _make_dishka_workload(container: Any, scope: ScopeMode) -> Callable[[], None]:
    if scope == "request":
        def workload() -> None:
            with container() as request_container:
                request_container.get(Application).start()

        return workload

    def workload() -> None:
        container.get(Application).start()

    return workload


def _build_dependency_injector_container(scope: ScopeMode):
    containers = importlib.import_module("dependency_injector.containers")
    providers = importlib.import_module("dependency_injector.providers")

    provider_cls = providers.Singleton if scope != "transient" else providers.Factory

    class PerfContainer(containers.DeclarativeContainer):
        config = provider_cls(Config)
        repository = provider_cls(Repository, config=config)
        service = provider_cls(Service, repository=repository)
        use_case = provider_cls(UseCase, service=service)
        controller = provider_cls(Controller, use_case=use_case)
        handler = provider_cls(Handler, controller=controller)
        middleware = provider_cls(Middleware, handler=handler)
        gateway = provider_cls(Gateway, middleware=middleware)
        facade = provider_cls(Facade, gateway=gateway)
        application = provider_cls(Application, facade=facade)

    return PerfContainer()


def _make_dependency_injector_workload(container: Any, scope: ScopeMode) -> Callable[[], None]:
    if scope == "request":
        def workload() -> None:
            container.repository.reset()
            container.service.reset()
            container.use_case.reset()
            container.controller.reset()
            container.handler.reset()
            container.middleware.reset()
            container.gateway.reset()
            container.facade.reset()
            container.application.reset()
            container.application().start()

        return workload

    def workload() -> None:
        container.application().start()

    return workload


def _build_anydi_target(
    scope: ScopeMode
) -> BenchmarkTarget:
    container = _build_anydi_container(scope)
    workload = _make_anydi_workload(container, scope)

    def cleanup() -> None:
        container.close()

    return BenchmarkTarget("anydi", workload, cleanup)


def _build_dishka_target(
    scope: ScopeMode
) -> BenchmarkTarget:
    container = _build_dishka_container(scope)
    workload = _make_dishka_workload(container, scope)

    def cleanup() -> None:
        container.close()

    return BenchmarkTarget("dishka", workload, cleanup)


def _build_dependency_injector_target(scope: ScopeMode) -> BenchmarkTarget:
    container = _build_dependency_injector_container(scope)
    workload = _make_dependency_injector_workload(container, scope)

    def cleanup() -> None:
        if hasattr(container, "shutdown_resources"):
            container.shutdown_resources()

    return BenchmarkTarget("dependency_injector", workload, cleanup)


def _benchmark(
    workload: Callable[[], None],
    *,
    iterations: int = ITERATIONS,
    repeats: int = REPEATS,
) -> float:
    runs: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(iterations):
            workload()
        runs.append(time.perf_counter() - start)
    return statistics.fmean(runs)


def compare_performance(
    *,
    iterations: int = ITERATIONS,
    repeats: int = REPEATS,
    scope: ScopeMode = "singleton",
) -> PerformanceResult:


    targets = [
        _build_anydi_target(scope),
        _build_dishka_target(scope),
        _build_dependency_injector_target(scope),
    ]

    for target in targets:
        target.workload()

    timings: dict[str, float] = {}
    try:
        for target in targets:
            timings[target.name] = _benchmark(
                target.workload, iterations=iterations, repeats=repeats
            )
    finally:
        for target in targets:
            target.cleanup()

    return PerformanceResult(
        anydi=timings["anydi"],
        dishka=timings["dishka"],
        dependency_injector=timings["dependency_injector"],
    )


def _format_report(result: PerformanceResult) -> str:
    return (
        "AnyDI: {anydi:.6f}s | Dishka: {dishka:.6f}s "
        "| dependency_injector: {di:.6f}s | AnyDI/Dishka: {ratio_anydi:.2f}x "
        "| AnyDI/dependency_injector: {ratio_di:.2f}x"
    ).format(
        anydi=result.anydi,
        dishka=result.dishka,
        di=result.dependency_injector,
        ratio_anydi=result.anydi_vs_dishka,
        ratio_di=result.anydi_vs_dependency_injector,
    )


if __name__ == "__main__":  # pragma: no cover - helper for manual runs
    for scope in ("singleton", "transient", "request"):
        result = compare_performance(scope=scope)
        print(f"[{scope}] {_format_report(result)}")
