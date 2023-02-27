import pyxdi

from tests.fixtures import Service


@pyxdi.inject
def b_handler(service: Service = pyxdi.dep) -> None:
    pass
