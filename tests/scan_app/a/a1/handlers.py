from anydi import injectable


@injectable(tags=["a", "a1"])
def a1_handler() -> None:
    pass
