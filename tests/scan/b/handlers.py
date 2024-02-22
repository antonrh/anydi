from dataclasses import dataclass

import initdi

from tests.fixtures import Service


@initdi.inject
def b_handler(service: Service = initdi.dep) -> None:
    pass


class BClassHandler:
    def __init__(self, service: Service = initdi.dep) -> None:
        self.service = service


@dataclass
class BDataclassHandler:
    service: Service = initdi.dep
