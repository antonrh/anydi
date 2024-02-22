import pyxdi


@pyxdi.inject(tags=["a", "a2", "a21"])
def a21_handler(message: str = pyxdi.dep) -> None:
    pass
