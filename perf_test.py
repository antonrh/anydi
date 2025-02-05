import dataclasses
import time
from functools import cached_property
from typing import NamedTuple, Annotated

from anydi import Container, auto
from anydi._utils import get_typed_parameters


@dataclasses.dataclass
class Repository:
    pass


@dataclasses.dataclass
class Service:
    repo: Repository


container = Container()


@container.provider(scope="singleton")
def service_1(repo: Repository) -> Annotated[Service, "service1"]:
    return Service(repo=repo)


@container.provider(scope="singleton")
def service_2(repo: Repository) -> Annotated[Service, "service2"]:
    return Service(repo=repo)


@container.provider(scope="singleton")
def service_3(repo: Repository) -> Annotated[Service, "service3"]:
    return Service(repo=repo)


@container.inject
def handler(
    service_1: Annotated[Service, "service1"] = auto,
    service_2: Annotated[Service, "service2"] = auto,
    service_3: Annotated[Service, "service3"] = auto,
) -> str:
    _, _, _ = service_1, service_2, service_3
    return ""


_ = handler()


start = time.time()

for _ in range(100_000):
    _ = handler()


print("Time: ", time.time() - start)


# 1 Time:  0.27786993980407715
# 2 Time:  0.24386978149414062
# 2 Time:  0.2397608757019043
