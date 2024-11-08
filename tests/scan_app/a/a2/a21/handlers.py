from anydi import auto, injectable


@injectable(tags=["a", "a2", "a21"])
def a21_handler(message: str = auto) -> None:
    pass
