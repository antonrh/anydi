import pyxdi


@pyxdi.injectable(tags=["a", "a2", "a21"])
def a21_handler(message: str = pyxdi.dep) -> None:
    pass
