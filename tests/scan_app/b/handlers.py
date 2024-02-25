from dataclasses import dataclass

from pyxdi import auto, inject

from tests.fixtures import Service


@inject
def b_handler(service: Service = auto()) -> None:
    pass


class BClassHandler:
    def __init__(self, service: Service = auto()) -> None:
        self.service = service


@dataclass
class BDataclassHandler:
    service: Service = auto()
