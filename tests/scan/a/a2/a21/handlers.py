import initdi


@initdi.inject(tags=["a", "a2", "a21"])
def a21_handler(message: str = initdi.dep) -> None:
    pass
