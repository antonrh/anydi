from pyxdi import PyxDI, Module, provider

class AppModule(Module):
    @provider(scope="singleton")
    def dep2(self, dep1: str) -> str:
        return f"dep2({dep1})"

    @provider(scope="singleton")
    def dep1(self) -> str:
        return "dep1"


di = PyxDI(modules=[AppModule()])


