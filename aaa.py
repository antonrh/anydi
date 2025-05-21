from __future__ import annotations

import time
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, Mapping, TypedDict
from typing_extensions import Required, TypeForm


def handle(b, a=1, c: "int" = 2) -> str:
    return a


@dataclass(kw_only=True, frozen=True)
class Parameter:
    name: str
    annotation: Any
    default: Any
    has_default: bool = False


@dataclass(kw_only=True, frozen=True)
class Signature:
    parameters: list[Parameter]
    return_annotation: Any
    has_return_annotation: bool = False

    @classmethod
    def from_call(
        cls,
        call: Callable[..., object] | type[Any] | ModuleType,
        *,
        globals: Mapping[str, Any] | None = None,
        locals: Mapping[str, Any] | None = None,
        eval_str: bool = False,
        strict: bool = False,
        include_defaults: bool = False,
        reject_positional_only: bool = False,
    ) -> Signature:
        if reject_positional_only:
            try:
                pos_count = call.__code__.co_posonlyargcount
                if pos_count > 0:
                    raise ValueError(
                        f"Positional-only arguments are not supported: {pos_count}"
                    )
            except AttributeError:
                pass

        annotations = get_annotations(
            call, globals=globals, locals=locals, eval_str=eval_str
        )

        if strict:
            # Check for missing type annotations
            arg_names = call.__code__.co_varnames[: call.__code__.co_argcount]
            for name in arg_names:
                if name not in annotations:
                    raise TypeError(f"Argument '{name}' is missing a type annotation")

            # Check for missing return type annotation
            if "return" not in annotations:
                raise TypeError("Return type annotation is missing")

        defaults = cls._get_defaults(call) if include_defaults else {}
        parameters = []
        return_annotation = None
        has_return_annotation = False

        for name, annotation in annotations.items():
            if name == "return":
                return_annotation = annotation
                has_return_annotation = True
                continue
            parameters.append(
                Parameter(
                    name=name,
                    annotation=annotation,
                    default=defaults.get(name, None),
                    has_default=include_defaults and name in defaults,
                )
            )

        return cls(
            parameters=parameters,
            return_annotation=return_annotation,
            has_return_annotation=has_return_annotation,
        )

    @staticmethod
    def _get_defaults(
        call: Callable[..., object] | type[Any] | ModuleType,
    ) -> dict[str, Any]:
        try:
            code = call.__code__
        except AttributeError:
            return {}

        arg_names = code.co_varnames[: code.co_argcount]
        defaults = call.__defaults__ or ()
        kwdefaults = call.__kwdefaults__ or {}
        all_defaults = {}
        pos_offset = len(arg_names) - len(defaults)

        # Calculate where defaults should start and map them to argument names
        all_defaults = {
            name: value for name, value in zip(arg_names[-len(defaults) :], defaults)
        }

        # Include keyword defaults
        all_defaults.update(kwdefaults)

        return all_defaults


s = time.time()

for _ in range(100000):
    Signature.from_call(handle, eval_str=True)


print(
    "Execution time for Signature.from_call with eval_str=True:",
    time.time() - s,
)
