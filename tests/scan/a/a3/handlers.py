import pyxdi

from tests.fixtures import Service


@pyxdi.inject
def a_a3_handler_1(message: str = pyxdi.dep) -> str:
    return message


def a_a3_handler_2(service: Service = pyxdi.dep) -> Service:
    return service
