"""Test module with @provided classes."""

from abc import ABC, abstractmethod

from anydi import provided, singleton, transient


@singleton
class SingletonService:
    """A singleton service."""

    def __init__(self) -> None:
        self.name = "singleton_service"


@transient
class TransientService:
    """A transient service."""

    def __init__(self, singleton_service: SingletonService) -> None:
        self.singleton_service = singleton_service
        self.name = "transient_service"


class IRepository(ABC):
    """Repository interface."""

    @abstractmethod
    def get(self, user_id: int) -> dict:
        pass


@provided(scope="singleton", alias=IRepository)
class UserRepository(IRepository):
    """User repository implementation."""

    def get(self, user_id: int) -> dict:
        return {"id": user_id, "name": "Alice"}
