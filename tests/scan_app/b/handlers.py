from dataclasses import dataclass

from anydi import Inject, injectable

from tests.fixtures import Service


@injectable
def b_handler(service: Service = Inject()) -> None:
    pass


class BClassHandler:
    def __init__(self, service: Service = Inject()) -> None:
        self.service = service


@dataclass
class BDataclassHandler:
    service: Service = Inject()
