"""AnyDI Typer extension."""

from __future__ import annotations

import functools
import inspect
from typing import Any

from typer import Typer

from anydi import Container

__all__ = ["install"]


def _process_callback(callback: Any, container: Container) -> Any:
    """Validate and wrap a callback for dependency injection."""
    if not callable(callback):
        return callback

    sig = inspect.signature(callback, eval_str=True)
    injected_param_names: set[str] = set()
    non_injected_params: set[inspect.Parameter] = set()

    # Validate parameters and collect which ones need injection
    for parameter in sig.parameters.values():
        _, should_inject = container.validate_injected_parameter(
            parameter, call=callback
        )
        if should_inject:
            injected_param_names.add(parameter.name)
        else:
            non_injected_params.add(parameter)

    # If no parameters need injection, return the original callback
    if not injected_param_names:
        return callback

    @functools.wraps(callback)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return container.run(callback, *args, **kwargs)

    # Update the wrapper's signature to only show non-injected parameters to Typer
    wrapper.__signature__ = sig.replace(parameters=non_injected_params)  # type: ignore

    return wrapper


def install(app: Typer, container: Container) -> None:
    """Install AnyDI into a Typer application."""
    # Process main callback if exists
    if app.registered_callback:
        callback = app.registered_callback.callback
        if callback:
            app.registered_callback.callback = _process_callback(callback, container)

    # Process all registered commands
    for command_info in app.registered_commands:
        callback = command_info.callback
        if callback:
            command_info.callback = _process_callback(callback, container)

    # Process nested Typer groups
    for group_info in app.registered_groups:
        # Recursively install for nested Typer apps
        if group_info.typer_instance:
            install(group_info.typer_instance, container)
