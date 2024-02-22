import initdi

from tests.fixtures import Service


class ScanModule(initdi.Module):
    @initdi.provider(scope="singleton")
    def a_a1_provider(self) -> str:
        return "a.a1.str_provider"

    @initdi.provider(scope="singleton")
    def a_a3_provider(self) -> int:
        return 10000

    @initdi.provider(scope="singleton")
    def b_service_provider(self, ident: str) -> Service:
        return Service(ident=ident)
