import asyncio

import pyxdi


class Service:
    def __init__(self, message: str) -> None:
        self.message = message


di = pyxdi.PyxDI(auto_register=True)


@di.provider
def message() -> str:
    print("call")
    return "Hello"


@di.inject
async def call_me(service: Service = pyxdi.dep) -> None:
    print(service.message)


async def main() -> None:
    await di.start()
    async with di.request_context() as ctx:
        await call_me()


if __name__ == '__main__':
    asyncio.run(main())

