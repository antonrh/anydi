from typing import Literal

Scope = Literal["transient", "singleton", "request"]

ALLOWED_SCOPES: dict[Scope, list[Scope]] = {
    "singleton": ["singleton"],
    "request": ["request", "singleton"],
    "transient": ["transient", "request", "singleton"],
}
