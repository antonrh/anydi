try:
    from ninja import operation
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "'django-ninja' is not installed. "
        "Please install it using 'pip install django-ninja'."
    ) from exc

from ._operation import AsyncOperation, Operation
from ._signature import ViewSignature


def patch_ninja() -> None:
    operation.ViewSignature = ViewSignature  # type: ignore[attr-defined]
    operation.Operation = Operation  # type: ignore[misc]
    operation.AsyncOperation = AsyncOperation  # type: ignore[misc]
