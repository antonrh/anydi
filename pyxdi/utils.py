import functools
import inspect
import sys
import typing as t

import anyio
from lazy_object_proxy import Proxy

T = t.TypeVar("T")

HAS_SIGNATURE_EVAL_STR_ARG = sys.version_info > (3, 9)


def get_full_qualname(obj: t.Any) -> str:
    qualname = getattr(obj, "__qualname__", f"unknown[{type(obj).__qualname__}]")
    module_name = getattr(obj, "__module__", "__main__")
    return f"{module_name}.{qualname}".removeprefix("builtins.")


@functools.lru_cache(maxsize=None)
def get_signature(obj: t.Callable[..., t.Any]) -> inspect.Signature:
    signature_kwargs: t.Dict[str, t.Any] = {}
    if HAS_SIGNATURE_EVAL_STR_ARG:
        signature_kwargs["eval_str"] = True
    return inspect.signature(obj, **signature_kwargs)


def is_builtin_type(tp: t.Type[t.Any]) -> bool:
    return tp.__module__ == "builtins"


def make_lazy(func: t.Callable[..., T], /, *args: t.Any, **kwargs: t.Any) -> T:
    return t.cast(T, Proxy(functools.partial(func, *args, **kwargs)))


async def run_async(func: t.Callable[..., T], /, *args: t.Any, **kwargs: t.Any) -> T:
    return await anyio.to_thread.run_sync(functools.partial(func, *args, **kwargs))
