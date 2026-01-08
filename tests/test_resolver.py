from anydi import Container, request, singleton


class TestResolver:
    def test_compile_with_removed_provider(self) -> None:
        @singleton
        class Dependency:
            pass

        @singleton
        class Service:
            def __init__(self, dep: Dependency) -> None:
                self.dep = dep

        container = Container()
        resolver = container._resolver

        container.register(Dependency, scope="singleton")
        service_provider = container.register(Service, scope="singleton")

        resolver.compile(service_provider, is_async=False)

        del container.providers[Dependency]

        resolver.compile(service_provider, is_async=False)

    def test_lazy_compile_with_removed_provider(self) -> None:
        @singleton
        class Dependency:
            pass

        @singleton
        class Service:
            def __init__(self, dep: Dependency) -> None:
                self.dep = dep

        container = Container()
        resolver = container._resolver

        container.register(Dependency, scope="singleton")
        container.register(Service, scope="singleton")

        service_provider = container.providers[Service]

        del container.providers[Dependency]

        resolver.clear_caches()
        resolver.compile(service_provider, is_async=False)

    def test_custom_scope_with_override(self) -> None:
        @request
        class Service:
            def __init__(self) -> None:
                self.name = "original"

        container = Container()
        container.register(Service, scope="request")
        resolver = container._resolver

        override_instance = Service()
        override_instance.name = "override"
        resolver.add_override(Service, override_instance)

        service_provider = container.providers[Service]
        resolver.compile(service_provider, is_async=False)

        resolver.remove_override(Service)
