"""Resolver compilation module for AnyDI."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, NamedTuple

import anyio.to_thread
from typing_extensions import type_repr

from ._provider import Provider
from ._types import NOT_SET, is_async_context_manager, is_context_manager

if TYPE_CHECKING:
    from ._container import Container


class CompiledResolver(NamedTuple):
    resolve: Any
    create: Any


class Resolver:
    def __init__(self, container: Container) -> None:
        self._container = container
        self._unresolved_interfaces: set[Any] = set()
        self._cache: dict[Any, CompiledResolver] = {}
        self._async_cache: dict[Any, CompiledResolver] = {}

        # Determine compilation flags based on whether methods are overridden
        self._has_override_support = callable(
            getattr(self._container, "_hook_override_for", None)
        )
        self._wrap_dependencies = callable(
            getattr(self._container, "_hook_wrap_dependency", None)
        )
        self._wrap_instance = callable(
            getattr(self._container, "_hook_post_resolve", None)
        )

    def add_unresolved(self, interface: Any) -> None:
        self._unresolved_interfaces.add(interface)

    def get_cached(self, interface: Any, *, is_async: bool) -> CompiledResolver | None:
        """Get cached resolver if it exists."""
        cache = self._async_cache if is_async else self._cache
        return cache.get(interface)

    def compile(self, provider: Provider, *, is_async: bool) -> CompiledResolver:
        """Compile an optimized resolver function for the given provider."""
        # Select the appropriate cache based on sync/async mode
        cache = self._async_cache if is_async else self._cache

        # Check if already compiled in cache
        if provider.interface in cache:
            return cache[provider.interface]

        # Recursively compile dependencies first
        for p in provider.parameters:
            if p.provider is not None:
                self.compile(p.provider, is_async=is_async)

        # Compile the resolver and creator functions
        compiled = self._compile_resolver(provider, is_async=is_async)

        # Store the compiled functions in the cache
        cache[provider.interface] = compiled

        return compiled

    def _compile_resolver(  # noqa: C901
        self, provider: Provider, *, is_async: bool
    ) -> CompiledResolver:
        """Compile optimized resolver functions for the given provider."""
        has_override_support = self._has_override_support
        wrap_dependencies = self._wrap_dependencies
        wrap_instance = self._wrap_instance
        num_params = len(provider.parameters)
        param_resolvers: list[Any] = [None] * num_params
        param_annotations: list[Any] = [None] * num_params
        param_defaults: list[Any] = [None] * num_params
        param_has_default: list[bool] = [False] * num_params
        param_names: list[str] = [""] * num_params
        unresolved_messages: list[str] = [""] * num_params

        cache = self._async_cache if is_async else self._cache

        for idx, p in enumerate(provider.parameters):
            param_annotations[idx] = p.annotation
            param_defaults[idx] = p.default
            param_has_default[idx] = p.has_default
            param_names[idx] = p.name

            if p.provider is not None:
                compiled = cache.get(p.provider.interface)
                if compiled is None:
                    compiled = self.compile(p.provider, is_async=is_async)
                    cache[p.provider.interface] = compiled
                param_resolvers[idx] = compiled.resolve

            msg = (
                f"You are attempting to get the parameter `{p.name}` with the "
                f"annotation `{type_repr(p.annotation)}` as a dependency into "
                f"`{type_repr(provider.call)}` which is not registered or set in the "
                "scoped context."
            )
            unresolved_messages[idx] = msg

        scope = provider.scope
        is_generator = provider.is_generator
        is_async_generator = provider.is_async_generator if is_async else False
        is_coroutine = provider.is_coroutine if is_async else False
        no_params = len(param_names) == 0

        create_lines: list[str] = []
        if is_async:
            create_lines.append(
                "async def _create_instance(container, context, store, defaults):"
            )
        else:
            create_lines.append(
                "def _create_instance(container, context, store, defaults):"
            )

        if no_params:
            # Fast path: no parameters to resolve, skip NOT_SET check
            if not is_async:
                create_lines.append("    if _is_async:")
                create_lines.append(
                    "        raise TypeError("
                    'f"The instance for the provider `{_provider_name}` '
                    'cannot be created in synchronous mode."'
                    ")"
                )
        else:
            # Need NOT_SET for parameter resolution
            create_lines.append("    NOT_SET_ = _NOT_SET")
            if not is_async:
                create_lines.append("    if _is_async:")
                create_lines.append(
                    "        raise TypeError("
                    'f"The instance for the provider `{_provider_name}` '
                    'cannot be created in synchronous mode."'
                    ")"
                )
            # Cache the resolver cache for faster repeated access
            create_lines.append("    cache = _cache")

        if not no_params:
            # Only generate parameter resolution logic if there are parameters
            for idx, name in enumerate(param_names):
                create_lines.append(f"    # resolve param `{name}`")
                create_lines.append(
                    f"    if defaults is not None and '{name}' in defaults:"
                )
                create_lines.append(f"        arg_{idx} = defaults['{name}']")
                create_lines.append("    else:")
                create_lines.append("        cached = NOT_SET_")
                create_lines.append("        if context is not None:")
                create_lines.append(
                    f"            cached = context.get(_param_annotations[{idx}])"
                )
                create_lines.append("        if cached is NOT_SET_:")
                create_lines.append(
                    f"            if _param_annotations[{idx}] in "
                    "_unresolved_interfaces:"
                )
                create_lines.append(
                    f"                raise LookupError(_unresolved_messages[{idx}])"
                )
                create_lines.append(f"            resolver = _param_resolvers[{idx}]")
                create_lines.append("            if resolver is None:")
                create_lines.append("                try:")
                if is_async:
                    create_lines.append(
                        f"                    compiled = "
                        f"cache.get(_param_annotations[{idx}])"
                    )
                    create_lines.append("                    if compiled is None:")
                    create_lines.append(
                        "                        provider = "
                        "container._get_or_register_provider("
                        f"_param_annotations[{idx}])"
                    )
                    create_lines.append(
                        "                        compiled = "
                        "_compile(provider, is_async=True)"
                    )
                    create_lines.append(
                        "                        cache[provider.interface] = compiled"
                    )
                    create_lines.append(
                        f"                    arg_{idx} = "
                        f"await compiled[0](container, context)"
                    )
                else:
                    create_lines.append(
                        f"                    compiled = "
                        f"cache.get(_param_annotations[{idx}])"
                    )
                    create_lines.append("                    if compiled is None:")
                    create_lines.append(
                        "                        provider = "
                        "container._get_or_register_provider(_param_annotations[{idx}])"
                    )
                    create_lines.append(
                        "                        compiled = "
                        "_compile(provider, is_async=False)"
                    )
                    create_lines.append(
                        "                        cache[provider.interface] = compiled"
                    )
                    create_lines.append(
                        f"                    arg_{idx} = "
                        f"compiled[0](container, context)"
                    )
                create_lines.append("                except LookupError:")
                create_lines.append(
                    f"                    if _param_has_default[{idx}]:"
                )
                create_lines.append(
                    f"                        arg_{idx} = _param_defaults[{idx}]"
                )
                create_lines.append("                    else:")
                create_lines.append("                        raise")
                create_lines.append("            else:")
                if is_async:
                    create_lines.append(
                        f"                arg_{idx} = await resolver("
                        f"container, context)"
                    )
                else:
                    create_lines.append(
                        f"                arg_{idx} = resolver(container, context)"
                    )
                create_lines.append("        else:")
                create_lines.append(f"            arg_{idx} = cached")
                if wrap_dependencies:
                    create_lines.append(
                        f"    arg_{idx} = container._hook_wrap_dependency("
                        f"_param_annotations[{idx}], arg_{idx})"
                    )

        # Handle different provider types
        if is_async and is_coroutine:
            # Async function - call with await
            if param_names:
                call_args = ", ".join(
                    f"{name}=arg_{idx}" for idx, name in enumerate(param_names)
                )
                create_lines.append("    if defaults is not None:")
                create_lines.append("        call_kwargs = {")
                for idx, name in enumerate(param_names):
                    create_lines.append(f"            '{name}': arg_{idx},")
                create_lines.append("        }")
                create_lines.append("        call_kwargs.update(defaults)")
                create_lines.append(
                    "        inst = await _provider_call(**call_kwargs)"
                )
                create_lines.append("    else:")
                create_lines.append(f"        inst = await _provider_call({call_args})")
            else:
                create_lines.append("    if defaults is not None:")
                create_lines.append("        inst = await _provider_call(**defaults)")
                create_lines.append("    else:")
                create_lines.append("        inst = await _provider_call()")
        elif is_async and is_async_generator:
            # Async generator - use async context manager
            create_lines.append("    if context is None:")
            create_lines.append(
                "        raise ValueError("
                '"The async stack is required for async generator providers.")'
            )
            if param_names:
                call_args = ", ".join(
                    f"{name}=arg_{idx}" for idx, name in enumerate(param_names)
                )
                create_lines.append("    if defaults is not None:")
                create_lines.append("        call_kwargs = {")
                for idx, name in enumerate(param_names):
                    create_lines.append(f"            '{name}': arg_{idx},")
                create_lines.append("        }")
                create_lines.append("        call_kwargs.update(defaults)")
                create_lines.append(
                    "        cm = _asynccontextmanager(_provider_call)(**call_kwargs)"
                )
                create_lines.append("    else:")
                create_lines.append(
                    f"        cm = _asynccontextmanager(_provider_call)({call_args})"
                )
            else:
                create_lines.append("    if defaults is not None:")
                create_lines.append(
                    "        cm = _asynccontextmanager(_provider_call)(**defaults)"
                )
                create_lines.append("    else:")
                create_lines.append(
                    "        cm = _asynccontextmanager(_provider_call)()"
                )
            create_lines.append("    inst = await context.aenter(cm)")
        elif is_generator:
            # Sync generator - use sync context manager
            create_lines.append("    if context is None:")
            create_lines.append(
                "        raise ValueError("
                '"The context is required for generator providers.")'
            )
            if param_names:
                call_args = ", ".join(
                    f"{name}=arg_{idx}" for idx, name in enumerate(param_names)
                )
                create_lines.append("    if defaults is not None:")
                create_lines.append("        call_kwargs = {")
                for idx, name in enumerate(param_names):
                    create_lines.append(f"            '{name}': arg_{idx},")
                create_lines.append("        }")
                create_lines.append("        call_kwargs.update(defaults)")
                create_lines.append(
                    "        cm = _contextmanager(_provider_call)(**call_kwargs)"
                )
                create_lines.append("    else:")
                create_lines.append(
                    f"        cm = _contextmanager(_provider_call)({call_args})"
                )
            else:
                create_lines.append("    if defaults is not None:")
                create_lines.append(
                    "        cm = _contextmanager(_provider_call)(**defaults)"
                )
                create_lines.append("    else:")
                create_lines.append("        cm = _contextmanager(_provider_call)()")
            if is_async:
                # In async mode, run sync context manager enter in thread
                create_lines.append("    inst = await _run_sync(context.enter, cm)")
            else:
                create_lines.append("    inst = context.enter(cm)")
        else:
            if param_names:
                call_args = ", ".join(
                    f"{name}=arg_{idx}" for idx, name in enumerate(param_names)
                )
                create_lines.append("    if defaults is not None:")
                create_lines.append("        call_kwargs = {")
                for idx, name in enumerate(param_names):
                    create_lines.append(f"            '{name}': arg_{idx},")
                create_lines.append("        }")
                create_lines.append("        call_kwargs.update(defaults)")
                create_lines.append("        inst = _provider_call(**call_kwargs)")
                create_lines.append("    else:")
                create_lines.append(f"        inst = _provider_call({call_args})")
            else:
                create_lines.append("    if defaults is not None:")
                create_lines.append("        inst = _provider_call(**defaults)")
                create_lines.append("    else:")
                create_lines.append("        inst = _provider_call()")

            # Handle context managers
            if is_async:
                create_lines.append(
                    "    if context is not None and _is_class and _is_acm(inst):"
                )
                create_lines.append("        await context.aenter(inst)")
                create_lines.append(
                    "    elif context is not None and _is_class and _is_cm(inst):"
                )
                create_lines.append("        await _run_sync(context.enter, inst)")
            else:
                create_lines.append(
                    "    if context is not None and _is_class and _is_cm(inst):"
                )
                create_lines.append("        context.enter(inst)")

        create_lines.append("    if context is not None and store:")
        create_lines.append("        context.set(_interface, inst)")

        if wrap_instance:
            create_lines.append(
                "    inst = container._hook_post_resolve(_interface, inst)"
            )
        create_lines.append("    return inst")

        resolver_lines: list[str] = []
        if is_async:
            resolver_lines.append("async def _resolver(container, context=None):")
        else:
            resolver_lines.append("def _resolver(container, context=None):")

        # Only define NOT_SET_ if we actually need it
        needs_not_set = has_override_support or scope in ("singleton", "request")
        if needs_not_set:
            resolver_lines.append("    NOT_SET_ = _NOT_SET")

        if scope == "singleton":
            resolver_lines.append("    if context is None:")
            resolver_lines.append("        context = container._singleton_context")
        elif scope == "request":
            resolver_lines.append("    if context is None:")
            resolver_lines.append("        context = container._get_request_context()")
        else:
            resolver_lines.append("    context = None")

        if has_override_support:
            resolver_lines.append(
                "    override = container._hook_override_for(_interface)"
            )
            resolver_lines.append("    if override is not NOT_SET_:")
            resolver_lines.append("        return override")

        if scope == "singleton":
            resolver_lines.append("    inst = context.get(_interface)")
            resolver_lines.append("    if inst is not NOT_SET_:")
            if wrap_instance:
                resolver_lines.append(
                    "        return container._hook_post_resolve(_provider, inst)"
                )
            else:
                resolver_lines.append("        return inst")

            if is_async:
                resolver_lines.append("    async with context.alock():")
            else:
                resolver_lines.append("    with context.lock():")
            resolver_lines.append("        inst = context.get(_interface)")
            resolver_lines.append("        if inst is not NOT_SET_:")
            if wrap_instance:
                resolver_lines.append(
                    "            return container._hook_post_resolve(_provider, inst)"
                )
            else:
                resolver_lines.append("            return inst")
            if is_async:
                resolver_lines.append(
                    "        return await "
                    "_create_instance(container, context, True, None)"
                )
            else:
                resolver_lines.append(
                    "        return _create_instance(container, context, True, None)"
                )
        elif scope == "request":
            resolver_lines.append("    inst = context.get(_interface)")
            resolver_lines.append("    if inst is not NOT_SET_:")
            if wrap_instance:
                resolver_lines.append(
                    "        return container._hook_post_resolve(_provider, inst)"
                )
            else:
                resolver_lines.append("        return inst")
            if is_async:
                resolver_lines.append(
                    "    return await _create_instance(container, context, True, None)"
                )
            else:
                resolver_lines.append(
                    "    return _create_instance(container, context, True, None)"
                )
        else:
            if is_async:
                resolver_lines.append(
                    "    return await _create_instance(container, None, False, None)"
                )
            else:
                resolver_lines.append(
                    "    return _create_instance(container, None, False, None)"
                )

        create_resolver_lines: list[str] = []
        if is_async:
            create_resolver_lines.append(
                "async def _resolver_create(container, defaults=None):"
            )
        else:
            create_resolver_lines.append(
                "def _resolver_create(container, defaults=None):"
            )

        # Only define NOT_SET_ if needed for override support
        if has_override_support:
            create_resolver_lines.append("    NOT_SET_ = _NOT_SET")

        if scope == "singleton":
            create_resolver_lines.append("    context = container._singleton_context")
        elif scope == "request":
            create_resolver_lines.append(
                "    context = container._get_request_context()"
            )
        else:
            create_resolver_lines.append("    context = None")

        if has_override_support:
            create_resolver_lines.append(
                "    override = container._hook_override_for(_interface)"
            )
            create_resolver_lines.append("    if override is not NOT_SET_:")
            create_resolver_lines.append("        return override")

        if scope == "singleton":
            if is_async:
                create_resolver_lines.append(
                    "    return await "
                    "_create_instance(container, context, False, defaults)"
                )
            else:
                create_resolver_lines.append(
                    "    return _create_instance(container, context, False, defaults)"
                )
        elif scope == "request":
            if is_async:
                create_resolver_lines.append(
                    "    return await "
                    "_create_instance(container, context, False, defaults)"
                )
            else:
                create_resolver_lines.append(
                    "    return _create_instance(container, context, False, defaults)"
                )
        else:
            if is_async:
                create_resolver_lines.append(
                    "    return await "
                    "_create_instance(container, None, False, defaults)"
                )
            else:
                create_resolver_lines.append(
                    "    return _create_instance(container, None, False, defaults)"
                )

        lines = create_lines + [""] + resolver_lines + [""] + create_resolver_lines

        src = "\n".join(lines)

        ns: dict[str, Any] = {
            "_provider": provider,
            "_interface": provider.interface,
            "_provider_call": provider.call,
            "_provider_name": provider.name,
            "_is_class": provider.is_class,
            "_param_annotations": param_annotations,
            "_param_defaults": param_defaults,
            "_param_has_default": param_has_default,
            "_param_resolvers": param_resolvers,
            "_unresolved_messages": unresolved_messages,
            "_unresolved_interfaces": self._unresolved_interfaces,
            "_NOT_SET": NOT_SET,
            "_contextmanager": contextlib.contextmanager,
            "_is_cm": is_context_manager,
            "_cache": self._async_cache if is_async else self._cache,
            "_compile": self._compile_resolver,
        }

        # Add async-specific namespace entries
        if is_async:
            ns["_asynccontextmanager"] = contextlib.asynccontextmanager
            ns["_is_acm"] = is_async_context_manager
            ns["_run_sync"] = anyio.to_thread.run_sync
        else:
            ns["_is_async"] = provider.is_async

        exec(src, ns)
        resolver = ns["_resolver"]
        creator = ns["_resolver_create"]

        return CompiledResolver(resolver, creator)
