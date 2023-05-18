import pyxdi

from tests.fixtures import Service


class ScanModule(pyxdi.Module):
    @pyxdi.provider
    def a_a1_provider(self) -> str:
        return "a.a1.str_provider"

    @pyxdi.provider
    def a_a3_provider(self) -> int:
        return 10000

    @pyxdi.provider
    def b_service_provider(self, ident: str) -> Service:
        return Service(ident=ident)
