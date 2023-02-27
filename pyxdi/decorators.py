import typing as t

ClassT = t.TypeVar("ClassT")


def transient(cls: ClassT) -> ClassT:
    setattr(cls, "__scope__", "transient")
    return cls


def request(cls: ClassT) -> ClassT:
    setattr(cls, "__scope__", "request")
    return cls


def singleton(cls: ClassT) -> ClassT:
    setattr(cls, "__scope__", "singleton")
    return cls
