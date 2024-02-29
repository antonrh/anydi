from dataclasses import dataclass

from anydi import dep, injectable

from tests.fixtures import Service


@injectable
def b_handler(service: Service = dep()) -> None:
    pass


class BClassHandler:
    def __init__(self, service: Service = dep()) -> None:
        self.service = service


@dataclass
class BDataclassHandler:
    service: Service = dep()
