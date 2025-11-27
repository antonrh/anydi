"""Test module with @provided classes."""

from anydi import singleton, transient


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
