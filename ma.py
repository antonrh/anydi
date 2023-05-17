import pyxdi


class Repository:
    pass


class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class AppModule(pyxdi.Module):
    def configure(self, di: pyxdi.PyxDI) -> None:
        di.singleton(Repository, Repository())

    @pyxdi.provider(scope="singleton")
    def configure_service(self, repo: Repository) -> Service:
        return Service(repo=repo)


di = pyxdi.PyxDI(modules=[AppModule()])

# or
# di.register_module(AppModule())

assert di.has_provider(Service)
assert di.has_provider(Repository)
