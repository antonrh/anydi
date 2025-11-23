"""Test that blocking function providers run in threads."""
import asyncio
import time

from anydi import Container

container = Container()


@container.provider(scope="transient")
async def blocking_function_provider() -> str:
    """This is a FUNCTION provider that does blocking I/O."""
    print("Blocking for 1s")
    await asyncio.sleep(1)
    return "OK"


async def main():
    """Run 3 concurrent calls - should take ~1s, not 3s."""
    await asyncio.gather(
        container.aresolve(str),
        container.aresolve(str),
        container.aresolve(str),
    )


if __name__ == '__main__':
    asyncio.run(main())
