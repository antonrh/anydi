import contextlib
import typing as t

from flask import Flask, Request, g, request

import pyxdi


def install(app: Flask) -> None:
    @app.before_request
    def enter_request_context() -> None:
        stack = contextlib.ExitStack()
        cm = pyxdi.request_context()
        ctx = stack.enter_context(cm)
        ctx.set(Request, request)
        g.pyxdi_request_context_stack = stack

    @app.teardown_request  # type: ignore
    def exit_request_context(exception: t.Optional[Exception]) -> None:
        stack = g.pop("pyxdi_request_context_stack", None)
        if stack:
            stack.close()
