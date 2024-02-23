from dataclasses import dataclass

import pyxdi

from tests.fixtures import Service


@pyxdi.injectable
def b_handler(service: Service = pyxdi.dep) -> None:
    pass


class BClassHandler:
    def __init__(self, service: Service = pyxdi.dep) -> None:
        self.service = service


@dataclass
class BDataclassHandler:
    service: Service = pyxdi.dep
