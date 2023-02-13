class Service:
    def __init__(self, ident: str) -> None:
        self.ident = ident
        self.events: list[str] = []
