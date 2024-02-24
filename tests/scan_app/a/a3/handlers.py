from pyxdi import dep, injectable

from tests.fixtures import Service


@injectable(tags=["inject"])
def a_a3_handler_1(message: str = dep) -> str:
    return message


def a_a3_handler_2(service: Service = dep) -> Service:
    return service
