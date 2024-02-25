from pyxdi import auto, inject

from tests.fixtures import Service


@inject(tags=["inject"])
def a_a3_handler_1(message: str = auto()) -> str:
    return message


def a_a3_handler_2(service: Service = auto()) -> Service:
    return service
