from dataclasses import dataclass
from unittest import mock

from anydi import Container

container = Container(strict=False, testing=True)
container.register(str, lambda: "Jonny", scope="singleton")


class Repository:
    def get_user(self):
        return {"name": "Jonny Cage"}


@dataclass(kw_only=True)
class Service:
    __scope__ = "singleton"

    repo: Repository
    name: str

    def get_user(self):
        return self.repo.get_user()



service = container.resolve(Service)

print(
    service.get_user(),
)

repo_mock = mock.MagicMock(spec=Repository)
repo_mock.get_user.return_value = {"name": "Jonny Mock"}

with container.override(Repository, repo_mock):
    print(
        service.get_user()
    )


