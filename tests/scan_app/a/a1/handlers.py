from anydi import Inject, injectable


@injectable(tags=["a", "a1"])
def a1_handler(name: str = Inject()) -> None:
    pass
