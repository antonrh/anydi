import initdi


@initdi.inject(tags=["a", "a1"])
def a1_handler() -> None:
    pass
