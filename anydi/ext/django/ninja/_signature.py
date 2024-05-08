from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from django.http import HttpResponse
from ninja.signature.details import (
    FuncParam,  # noqa
    ViewSignature as BaseViewSignature,
)
from ninja.signature.utils import get_path_param_names, get_typed_signature

from anydi._types import Marker  # noqa


class ViewSignature(BaseViewSignature):
    def __init__(self, path: str, view_func: Callable[..., Any]) -> None:
        self.view_func = view_func
        self.signature = get_typed_signature(self.view_func)
        self.path = path
        self.path_params_names = get_path_param_names(path)
        self.docstring = inspect.cleandoc(view_func.__doc__ or "")
        self.has_kwargs = False
        self.dependencies = []

        self.params = []
        for name, arg in self.signature.parameters.items():
            if name == "request":
                # TODO: maybe better assert that 1st param is request or check by type?
                # maybe even have attribute like `has_request`
                # so that users can ignore passing request if not needed
                continue

            if arg.kind == arg.VAR_KEYWORD:
                # Skipping **kwargs
                self.has_kwargs = True
                continue

            if arg.kind == arg.VAR_POSITIONAL:
                # Skipping *args
                continue

            if arg.annotation is HttpResponse:
                self.response_arg = name
                continue

            # Skip default values that are anydi dependency markers
            if isinstance(arg.default, Marker):
                self.dependencies.append((name, arg.annotation))
                continue

            func_param = self._get_param_type(name, arg)
            self.params.append(func_param)

        if hasattr(view_func, "_ninja_contribute_args"):
            for p_name, p_type, p_source in view_func._ninja_contribute_args:  # noqa
                self.params.append(
                    FuncParam(p_name, p_source.alias or p_name, p_source, p_type, False)
                )

        self.models = self._create_models()

        self._validate_view_path_params()
