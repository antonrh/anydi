import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pyxdi
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection, \
    AsyncSession
from sqlalchemy.orm import MappedAsDataclass, DeclarativeBase, Mapped, mapped_column


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    name: Mapped[str]


@dataclass
class UserRepository:
    session: AsyncSession

    def add(self, user: User) -> None:
        self.session.add(user)

    async def get(self, ident: int) -> User | None:
        return await self.session.get(User, ident=ident)


@dataclass
class UserService:
    user_repo: UserRepository

    async def get_user(self, user_id: int) -> User | None:
        return await self.user_repo.get(user_id)



di = pyxdi.PyxDI()


@di.provider(scope="singleton")
async def engine() -> AsyncIterator[AsyncEngine]:
    print("CREATE ENGINE")
    engine = create_async_engine(url="sqlite+aiosqlite:///pyxdi.db", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@di.provider(scope="request")
async def conn(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    print("CREATE CONN")
    async with engine.connect() as conn:
        yield conn


@di.provider(scope="request")
async def session(conn: AsyncConnection) -> AsyncIterator[AsyncSession]:
    print("CREATE SESSION")
    async with AsyncSession(bind=conn) as session:
        yield session


@di.provider(scope="request")
def user_repo(session: AsyncSession) -> UserRepository:
    print("CREATE user_repo")
    return UserRepository(session=session)


@di.provider(scope="request")
def user_service(user_repo: UserRepository) -> UserService:
    print("CREATE user_service")
    return UserService(user_repo=user_repo)


@di.inject
async def handler(user_service: UserService = pyxdi.dep) -> None:
    print(
        await user_service.get_user(10)
    )


async def main() -> None:
    # await di.astart()

    async with di.arequest_context():
        await handler()

    await di.aclose()


if __name__ == '__main__':
    asyncio.run(main())
