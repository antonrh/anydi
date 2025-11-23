import anyio
import pytest

from anydi._async_lock import AsyncRLock


@pytest.mark.anyio
async def test_async_rlock_context_manager_is_reentrant() -> None:
    lock = AsyncRLock()

    async with lock:
        async with lock:
            # acquiring twice in the same task should succeed without blocking
            await anyio.sleep(0)


@pytest.mark.anyio
async def test_async_rlock_allows_manual_reentrancy() -> None:
    lock = AsyncRLock()

    await lock.acquire()
    await lock.acquire()

    lock.release()
    lock.release()


@pytest.mark.anyio
async def test_async_rlock_disallows_release_from_other_task() -> None:
    lock = AsyncRLock()

    async def owner() -> None:
        await lock.acquire()
        await anyio.sleep(0.1)
        lock.release()

    async def intruder() -> None:
        await anyio.sleep(0)
        with pytest.raises(RuntimeError):
            lock.release()

    async with anyio.create_task_group() as tg:
        tg.start_soon(owner)
        tg.start_soon(intruder)
