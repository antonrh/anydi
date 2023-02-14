from ._types import ClassT


def transient(cls: ClassT) -> ClassT:
    setattr(cls, "__autobind_scope__", "transient")
    return cls


def request(cls: ClassT) -> ClassT:
    setattr(cls, "__autobind_scope__", "request")
    return cls


def singleton(cls: ClassT) -> ClassT:
    setattr(cls, "__autobind_scope__", "singleton")
    return cls
