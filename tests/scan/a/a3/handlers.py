import initdi

from tests.fixtures import Service


@initdi.inject(tags=["inject"])
def a_a3_handler_1(message: str = initdi.dep) -> str:
    return message


def a_a3_handler_2(service: Service = initdi.dep) -> Service:
    return service
