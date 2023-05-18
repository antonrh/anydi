import asyncio

import lazy_object_proxy
import inspect


async def lol():
    print("CALL")
    return "OK"


ok = lazy_object_proxy.Proxy(lol)

async def main():
    if inspect.isawaitable(ok):
        await ok


asyncio.run(main())
