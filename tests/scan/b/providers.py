import pyxdi

from tests.fixtures import Service


@pyxdi.provider
def b_service_provider(ident: str) -> Service:
    return Service(ident=ident)
