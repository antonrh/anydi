from pyxdi import Container, auto


container = Container()


@container.provider(scope="singleton")
def str_provider() -> str:
    return "Hello, World!"


@container.inject
def handler(message: str = auto()) -> None:
    print(message)


if __name__ == '__main__':
    handler()
