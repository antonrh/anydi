from dataclasses import dataclass

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

from pyxdi import PyxDI, dep, singleton
import time



@singleton
class Repository:
    pass

@singleton
class Repository1:
    pass


@singleton
class Repository2:
    pass


@singleton
class Repository3:
    pass


@singleton
class Repository4:
    pass


@singleton
class Repository5:
    pass

@dataclass
class Service:
    repo: Repository
    repo1: Repository1
    repo2: Repository2
    repo3: Repository3
    repo4: Repository4
    repo5: Repository5


class Container(containers.DeclarativeContainer):

    repo = providers.Singleton(Repository)
    repo1 = providers.Singleton(Repository1)
    repo2 = providers.Singleton(Repository2)
    repo3 = providers.Singleton(Repository3)
    repo4 = providers.Singleton(Repository4)
    repo5 = providers.Singleton(Repository5)

    service = providers.Singleton(
        Service,
        repo=repo,
        repo1=repo1,
        repo2=repo2,
        repo3=repo3,
        repo4=repo4,
        repo5=repo5,
    )


services = {
    f"service{n}": type(f"Service{n}", (), {})()
    for n in range(1000)
}



di = PyxDI(auto_register=True)


@di.inject
def handler(service: Service = dep):
    pass


@inject
def handler1(service: Service = Provide[Container.service]):
    pass


start = time.time()

for _ in range(1000000):
    handler()
    # handler1()

end = time.time()

print("Elapsed (after compilation) = %s" % (end - start))
