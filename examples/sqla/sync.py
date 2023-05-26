from dataclasses import dataclass
from typing import Iterator

from sqlalchemy import Engine, create_engine, Connection

import pyxdi
from sqlalchemy.orm import MappedAsDataclass, DeclarativeBase, Mapped, mapped_column, \
    Session


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    name: Mapped[str]


@dataclass
class UserRepository:
    session: Session

    def add(self, user: User) -> None:
        self.session.add(user)

    def get(self, ident: int) -> User | None:
        return self.session.get(User, ident=ident)


@dataclass
class UserService:
    user_repo: UserRepository

    def get_user(self, user_id: int) -> User | None:
        return self.user_repo.get(user_id)



di = pyxdi.PyxDI()


@di.provider(scope="singleton")
def engine() -> Iterator[Engine]:
    print("CREATE ENGINE")
    engine = create_engine(url="sqlite:///pyxdi.db", echo=True)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@di.provider(scope="request")
def conn(engine: Engine) -> Iterator[Connection]:
    print("CREATE CONN")
    with engine.connect() as conn:
        yield conn

@di.provider(scope="request")
def session(conn: Connection) -> Iterator[Session]:
    with Session(bind=conn) as session:
        yield session


@di.provider(scope="request")
def user_repo(session: Session) -> UserRepository:
    return UserRepository(session=session)


@di.provider(scope="request")
def user_service(user_repo: UserRepository) -> UserService:
    return UserService(user_repo=user_repo)


@di.inject
def handler(user_service: UserService = pyxdi.dep) -> None:
    print(
        user_service.get_user(10)
    )


def main() -> None:
    di.start()

    with di.request_context():
        handler()

    di.close()


if __name__ == '__main__':
    main()
