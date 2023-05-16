import pyxdi
import inspect



class Client:
    def __init__(self, name: str) -> None:
        self.name = name


class AppModule(pyxdi.Module):
    @pyxdi.provider
    def client(self) -> Client:
        return Client(name="test")


di = pyxdi.PyxDI()
di.register_module(AppModule())

print(di.get(Client).name)

