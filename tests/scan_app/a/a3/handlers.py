from anydi import auto, injectable

from tests.fixtures import Service


@injectable(tags=["inject"])
def a_a3_handler_1(message: str = auto) -> str:
    return message


def a_a3_handler_2(service: Service = auto) -> Service:
    return service
