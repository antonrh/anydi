import typing as t


class Service:
    pass


def dep1() -> Service:
    return Service()


def dep2() -> list[Service]:
    return [Service()]


def dep3() -> t.Iterable[Service]:
    yield Service()


async def dep4() -> t.AsyncIterator[Service]:
    yield Service()
