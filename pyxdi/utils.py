import typing as t


def get_qualname(obj: t.Any) -> str:
    qualname = obj.__qualname__
    module_name = getattr(obj, "__module__", "__main__")
    return f"{module_name}.{qualname}".removeprefix("builtins.")
