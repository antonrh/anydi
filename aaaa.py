import time
from dataclasses import dataclass

from anydi import Container, auto

container = Container()


@dataclass
class Item:
    name: str


@dataclass
class Repo:
    items: list[Item]

    def all(self) -> list[Item]:
        return self.items

@dataclass
class Service:
    repo: Repo

    def get_items(self) -> list[Item]:
        return self.repo.all()




@container.provider(scope="transient")
def provide_repo() -> Repo:
    return Repo(items=[Item(name="item1"), Item(name="item2")])


@container.inject
def handler(service: Service = auto) -> None:
    _ = service.get_items()


start = time.time()

for _ in range(100000):
    handler()

print(time.time() - start)


# Time is 0.3882 seconds
