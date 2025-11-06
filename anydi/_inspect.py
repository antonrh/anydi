import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from typing_extensions import Sentinel, get_annotations

NOT_SET = Sentinel("NOT_SET")


@dataclass(kw_only=True)
class Parameter:
    name: str
    annotation: Any
    default: Any = NOT_SET

    @property
    def has_default(self) -> bool:
        return self.default is not NOT_SET


@dataclass(kw_only=True)
class Signature:
    parameters: list[Parameter]
    return_annotation: Any = NOT_SET

    @property
    def has_return_annotation(self) -> bool:
        return self.return_annotation is not NOT_SET


def get_signature(obj: Callable[..., Any]) -> Signature:
    """Return a Signature object for the given object."""
    if inspect.isclass(obj):
        obj = obj.__init__
    annotations = get_annotations(obj, eval_str=True)
    defaults = get_defaults(obj)
    parameters: list[Parameter] = []
    signature = Signature(parameters=parameters)
    for name, annotation in annotations.items():
        if name == "return":
            signature.return_annotation = annotation
            continue
        parameter = Parameter(name=name, annotation=annotation)
        if name in defaults:
            parameter.default = defaults[name]
        parameters.append(parameter)
    return signature


def get_defaults(obj: Callable[..., Any]) -> dict[str, Any]:
    """Return a dictionary of default values for the given object."""
    code = obj.__code__
    arg_names = code.co_varnames[: code.co_argcount]
    defaults = obj.__defaults__ or ()
    kwdefaults = obj.__kwdefaults__ or {}

    # Map positional-or-keyword defaults
    default_offset = len(arg_names) - len(defaults)
    defaults_map = {
        arg_names[i + default_offset]: defaults[i] for i in range(len(defaults))
    }

    # Merge keyword-only defaults
    defaults_map.update(kwdefaults)

    return defaults_map
