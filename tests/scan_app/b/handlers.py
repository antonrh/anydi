from dataclasses import dataclass

from anydi import auto, injectable

from tests.fixtures import Service


@injectable
def b_handler(service: Service = auto) -> None:
    pass


class BClassHandler:
    def __init__(self, service: Service = auto) -> None:
        self.service = service


@dataclass
class BDataclassHandler:
    service: Service = auto
