import uuid
from dataclasses import dataclass, field


@dataclass(kw_only=True)
class User:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    email: str
