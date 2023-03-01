import typing as t
import uuid
from dataclasses import dataclass, field

UserId = t.NewType("UserId", uuid.UUID)


@dataclass
class User:
    email: str
    id: UserId = field(default_factory=lambda: UserId(uuid.uuid4()))
