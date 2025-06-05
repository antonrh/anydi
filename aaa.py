from anydi.testcontainer import TestContainer


class Repo:
    def __init__(self, name: str) -> None:
        self.name = name


class Service:
    def __init__(self, repo: Repo = Repo("default")):
        self.repo = repo

    @property
    def repo_name(self) -> str:
        return self.repo.name


container = TestContainer()

with container.override(Repo, Repo("overridden")):
    service = container.resolve(Service)

    print(service.repo_name)
