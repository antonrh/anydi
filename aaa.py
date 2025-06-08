from anydi import Container
from anydi.testcontainer import TestContainer


def init_container(testing: bool = False) -> Container:
    container = Container()
    if testing:
        return TestContainer.from_container(container)
    return container
