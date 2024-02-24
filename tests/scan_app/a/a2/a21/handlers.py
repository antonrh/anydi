from pyxdi import dep, injectable


@injectable(tags=["a", "a2", "a21"])
def a21_handler(message: str = dep) -> None:
    pass
