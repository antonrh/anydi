import pyxdi


class Service:
    def __init__(self, name: str) -> None:
        self.name = name


di = pyxdi.PyxDI()


@di.provider
def service() -> Service:
    return Service(name="demo")


@di.inject
def handler(service: Service = pyxdi.dep) -> None:
    print(f"Hello, from service `{service.name}`")


handler()
