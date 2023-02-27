import pyxdi


@pyxdi.inject
def a21_handler(message: str = pyxdi.dep) -> None:
    pass
