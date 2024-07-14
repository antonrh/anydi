class Service:
    def __init__(self, ident: str) -> None:
        self.ident = ident
        self.events: list[str] = []


class Resource:
    def __init__(self) -> None:
        self.called = False
        self.committed = False
        self.rolled_back = False

    def run(self) -> None:
        self.called = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
