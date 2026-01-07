from anydi import Inject, injectable


@injectable(tags=["a", "a2", "a21"])
def a21_handler(message: str = Inject()) -> None:
    pass
