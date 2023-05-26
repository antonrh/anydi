import asyncio
import datetime
from typing import Annotated

import pyxdi

di = pyxdi.PyxDI()


@di.provider
def dep1() -> Annotated[str, "dep1"]:
    print("call dep1")
    return "dep1"


@di.provider
def dep2(dep1: Annotated[str, "dep1"]) -> Annotated[str, "dep2"]:
    print("call dep2")
    return dep1 + "dep2"



@di.inject
def handler(dep2: Annotated[str, "dep2"] = pyxdi.dep):
    pass

async def main():
    s = datetime.datetime.utcnow()
    for n in range(10_000_000):
        handler()
    print("time: ", (datetime.datetime.utcnow() - s).total_seconds())


if __name__ == '__main__':
    asyncio.run(main())
