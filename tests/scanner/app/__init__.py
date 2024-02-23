import pyxdi

from tests.fixtures import Service


class AppModule(pyxdi.Module):
    @pyxdi.provider(scope="singleton")
    def a_a1_provider(self) -> str:
        return "a.a1.str_provider"

    @pyxdi.provider(scope="singleton")
    def a_a3_provider(self) -> int:
        return 10000

    @pyxdi.provider(scope="singleton")
    def b_service_provider(self, ident: str) -> Service:
        return Service(ident=ident)
