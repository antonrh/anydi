from pyxdi import inject


@inject(tags=["a", "a1"])
def a1_handler() -> None:
    pass
