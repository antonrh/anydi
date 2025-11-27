from dataclasses import dataclass

from anydi import Provide, injectable

from tests.fixtures import Service


@injectable
def b_handler(service: Provide[Service]) -> None:
    pass


class BClassHandler:
    def __init__(self, service: Provide[Service]) -> None:
        self.service = service


@dataclass
class BDataclassHandler:
    service: Provide[Service]
