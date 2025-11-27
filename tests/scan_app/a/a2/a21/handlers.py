from anydi import Provide, injectable


@injectable(tags=["a", "a2", "a21"])
def a21_handler(message: Provide[str]) -> None:
    pass
