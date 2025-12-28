"""Resolver compilation module for AnyDI."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, NamedTuple

import anyio.to_thread
import wrapt  # type: ignore
from typing_extensions import type_repr

from ._provider import Provider
from ._types import NOT_SET, is_async_context_manager, is_context_manager

if TYPE_CHECKING:
    from ._container import Container


class InstanceProxy(wrapt.ObjectProxy):  # type: ignore
    """Proxy for dependency instances to enable override support."""

    def __init__(self, wrapped: Any, *, interface: type[Any]) -> None:
        super().__init__(wrapped)  # type: ignore
        self._self_interface = interface

    @property
    def interface(self) -> type[Any]:
        return self._self_interface


class CompiledResolver(NamedTuple):
    resolve: Any
    create: Any


class Resolver:
    def __init__(self, container: Container) -> None:
        self._container = container
        self._unresolved_interfaces: set[Any] = set()
        # Normal caches (fast path, no override checks)
        self._cache: dict[Any, CompiledResolver] = {}
        self._async_cache: dict[Any, CompiledResolver] = {}
        # Override caches (with override support)
        self._override_cache: dict[Any, CompiledResolver] = {}
        self._async_override_cache: dict[Any, CompiledResolver] = {}
        # Override instances storage
        self._override_instances: dict[Any, Any] = {}

    @property
    def override_mode(self) -> bool:
        """Check if override mode is enabled."""
        return bool(self._override_instances)

    def add_override(self, interface: Any, instance: Any) -> None:
        """Add an override instance for an interface."""
        self._override_instances[interface] = instance

    def remove_override(self, interface: Any) -> None:
        """Remove an override instance for an interface."""
        self._override_instances.pop(interface, None)

    def add_unresolved(self, interface: Any) -> None:
        self._unresolved_interfaces.add(interface)

    def get_cached(self, interface: Any, *, is_async: bool) -> CompiledResolver | None:
        """Get cached resolver if it exists."""
        if self.override_mode:
            cache = self._async_override_cache if is_async else self._override_cache
        else:
            cache = self._async_cache if is_async else self._cache
        return cache.get(interface)

    def compile(self, provider: Provider, *, is_async: bool) -> CompiledResolver:
        """Compile an optimized resolver function for the given provider."""
        # Select the appropriate cache based on sync/async mode and override mode
        if self.override_mode:
            cache = self._async_override_cache if is_async else self._override_cache
        else:
            cache = self._async_cache if is_async else self._cache

        # Check if already compiled in cache
        if provider.interface in cache:
            return cache[provider.interface]

        # Recursively compile dependencies first
        for p in provider.parameters:
            if p.provider is not None:
                self.compile(p.provider, is_async=is_async)

        # Compile the resolver and creator functions
        compiled = self._compile_resolver(
            provider, is_async=is_async, with_override=self.override_mode
        )

        # Store the compiled functions in the cache
        cache[provider.interface] = compiled

        return compiled

    def _add_override_check(
        self, lines: list[str], *, include_not_set: bool = False
    ) -> None:
        """Add override checking code to generated resolver."""
        lines.append("    override_mode = resolver.override_mode")
        lines.append("    if override_mode:")
        if include_not_set:
            lines.append("        NOT_SET_ = _NOT_SET")
        lines.append("        override = resolver._get_override_for(_interface)")
        lines.append("        if override is not NOT_SET_:")
        lines.append("            return override")

    def _add_create_call(
        self,
        lines: list[str],
        *,
        is_async: bool,
        with_override: bool,
        context: str,
        store: bool,
        defaults: str = "None",
        indent: str = "    ",
    ) -> None:
        """Add _create_instance call to generated resolver."""
        override_arg = "override_mode" if with_override else "False"
        context_arg = context if context else "None"
        store_arg = "True" if store else "False"

        if is_async:
            lines.append(
                f"{indent}return await _create_instance("
                f"container, {context_arg}, {store_arg}, {defaults}, {override_arg})"
            )
        else:
            lines.append(
                f"{indent}return _create_instance("
                f"container, {context_arg}, {store_arg}, {defaults}, {override_arg})"
            )

    def _compile_resolver(  # noqa: C901
        self, provider: Provider, *, is_async: bool, with_override: bool = False
    ) -> CompiledResolver:
        """Compile optimized resolver functions for the given provider."""
        num_params = len(provider.parameters)
        param_resolvers: list[Any] = [None] * num_params
        param_annotations: list[Any] = [None] * num_params
        param_defaults: list[Any] = [None] * num_params
        param_has_default: list[bool] = [False] * num_params
        param_names: list[str] = [""] * num_params
        param_shared_scopes: list[bool] = [False] * num_params
        unresolved_messages: list[str] = [""] * num_params

        cache = (
            (self._async_override_cache if is_async else self._override_cache)
            if with_override
            else (self._async_cache if is_async else self._cache)
        )

        for idx, p in enumerate(provider.parameters):
            param_annotations[idx] = p.annotation
            param_defaults[idx] = p.default
            param_has_default[idx] = p.has_default
            param_names[idx] = p.name
            param_shared_scopes[idx] = p.shared_scope

            if p.provider is not None:
                compiled = cache.get(p.provider.interface)
                if compiled is None:
                    compiled = self.compile(p.provider, is_async=is_async)
                    cache[p.provider.interface] = compiled
                param_resolvers[idx] = compiled.resolve

            unresolved_message = (
                f"You are attempting to get the parameter `{p.name}` with the "
                f"annotation `{type_repr(p.annotation)}` as a dependency into "
                f"`{type_repr(provider.call)}` which is not registered or set in the "
                "scoped context."
            )
            unresolved_messages[idx] = unresolved_message

        scope = provider.scope
        is_generator = provider.is_generator
        is_async_generator = provider.is_async_generator if is_async else False
        is_coroutine = provider.is_coroutine if is_async else False
        no_params = len(param_names) == 0

        create_lines: list[str] = []
        if is_async:
            create_lines.append(
                "async def _create_instance("
                "container, context, store, defaults, override_mode):"
            )
        else:
            create_lines.append(
                "def _create_instance("
                "container, context, store, defaults, override_mode):"
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
                # Direct dict access for shared scope params (avoids method call)
                if param_shared_scopes[idx]:
                    create_lines.append(
                        f"        cached = (context._instances.get("
                        f"_param_annotations[{idx}], NOT_SET_) "
                        f"if context is not None else NOT_SET_)"
                    )
                else:
                    create_lines.append("        cached = NOT_SET_")
                create_lines.append("        if cached is NOT_SET_:")
                create_lines.append(
                    f"            if _param_annotations[{idx}] in "
                    "_unresolved_interfaces:"
                )
                create_lines.append(
                    f"                raise LookupError(_unresolved_messages[{idx}])"
                )
                create_lines.append(
                    f"            _dep_resolver = _param_resolvers[{idx}]"
                )
                create_lines.append("            if _dep_resolver is None:")
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
                        f"await compiled[0](container, "
                        f"context if _param_shared_scopes[{idx}] else None)"
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
                        f"compiled[0](container, "
                        f"context if _param_shared_scopes[{idx}] else None)"
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
                        f"                arg_{idx} = await _dep_resolver("
                        f"container, "
                        f"context if _param_shared_scopes[{idx}] else None)"
                    )
                else:
                    create_lines.append(
                        f"                arg_{idx} = _dep_resolver("
                        f"container, "
                        f"context if _param_shared_scopes[{idx}] else None)"
                    )
                create_lines.append("        else:")
                create_lines.append(f"            arg_{idx} = cached")
                # Wrap dependencies if in override mode (only for override version)
                if with_override:
                    create_lines.append("    if override_mode:")
                    create_lines.append(
                        f"        arg_{idx} = resolver._wrap_for_override("
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
        create_lines.append("        context._instances[_interface] = inst")

        # Wrap instance if in override mode (only for override version)
        if with_override:
            create_lines.append("    if override_mode:")
            create_lines.append(
                "        inst = resolver._post_resolve_override(_interface, inst)"
            )
        create_lines.append("    return inst")

        resolver_lines: list[str] = []
        if is_async:
            resolver_lines.append("async def _resolver(container, context=None):")
        else:
            resolver_lines.append("def _resolver(container, context=None):")

        # Only define NOT_SET_ if we actually need it
        needs_not_set = scope != "transient"
        if needs_not_set:
            resolver_lines.append("    NOT_SET_ = _NOT_SET")

        if scope == "singleton":
            resolver_lines.append("    if context is None:")
            resolver_lines.append("        context = container._singleton_context")
        elif scope == "transient":
            resolver_lines.append("    context = None")
        else:
            # Custom scopes (including "request")
            # Inline context retrieval to avoid method call overhead
            resolver_lines.append("    if context is None:")
            resolver_lines.append("        try:")
            resolver_lines.append("            context = _scoped_context_var.get()")
            resolver_lines.append("        except LookupError:")
            resolver_lines.append(
                f"            raise LookupError("
                f"'The {scope} context has not been started. "
                f"Please ensure that the {scope} context is properly initialized "
                f"before attempting to use it.')"
            )

        if scope == "singleton":
            if with_override:
                self._add_override_check(resolver_lines)

            # Fast path: check cached instance
            resolver_lines.append("    inst = context.get(_interface)")
            resolver_lines.append("    if inst is not NOT_SET_:")
            resolver_lines.append("        return inst")

            if is_async:
                resolver_lines.append("    async with context.alock():")
            else:
                resolver_lines.append("    with context.lock():")
            resolver_lines.append("        inst = context.get(_interface)")
            resolver_lines.append("        if inst is not NOT_SET_:")
            resolver_lines.append("            return inst")
            self._add_create_call(
                resolver_lines,
                is_async=is_async,
                with_override=with_override,
                context="context",
                store=True,
                indent="        ",
            )
        elif scope == "transient":
            # Transient scope
            if with_override:
                self._add_override_check(resolver_lines, include_not_set=True)

            self._add_create_call(
                resolver_lines,
                is_async=is_async,
                with_override=with_override,
                context="",
                store=False,
            )
        else:
            # Custom scopes (including "request")
            if with_override:
                self._add_override_check(resolver_lines)

            # Fast path: check cached instance (inline dict access for speed)
            resolver_lines.append(
                "    inst = context._instances.get(_interface, NOT_SET_)"
            )
            resolver_lines.append("    if inst is not NOT_SET_:")
            resolver_lines.append("        return inst")

            self._add_create_call(
                resolver_lines,
                is_async=is_async,
                with_override=with_override,
                context="context",
                store=True,
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

        if with_override:
            # Cache override mode check
            create_resolver_lines.append("    override_mode = resolver.override_mode")

        if scope == "singleton":
            create_resolver_lines.append("    context = container._singleton_context")
        elif scope == "transient":
            create_resolver_lines.append("    context = None")
        else:
            # Custom scopes (including "request")
            # Inline context retrieval to avoid method call overhead
            create_resolver_lines.append("    try:")
            create_resolver_lines.append("        context = _scoped_context_var.get()")
            create_resolver_lines.append("    except LookupError:")
            create_resolver_lines.append(
                f"        raise LookupError("
                f"'The {scope} context has not been started. "
                f"Please ensure that the {scope} context is properly initialized "
                f"before attempting to use it.')"
            )

        if with_override:
            self._add_override_check(create_resolver_lines, include_not_set=True)

        # Determine context for create call
        context_arg = "context" if scope != "transient" else ""

        self._add_create_call(
            create_resolver_lines,
            is_async=is_async,
            with_override=with_override,
            context=context_arg,
            store=False,
            defaults="defaults",
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
            "_param_shared_scopes": param_shared_scopes,
            "_unresolved_messages": unresolved_messages,
            "_unresolved_interfaces": self._unresolved_interfaces,
            "_NOT_SET": NOT_SET,
            "_contextmanager": contextlib.contextmanager,
            "_is_cm": is_context_manager,
            "_cache": (
                (self._async_override_cache if is_async else self._override_cache)
                if with_override
                else (self._async_cache if is_async else self._cache)
            ),
            "_compile": self._compile_resolver,
            "resolver": self,
        }

        # For custom scopes, cache the ContextVar to avoid dictionary lookups
        if scope not in ("singleton", "transient"):
            ns["_scoped_context_var"] = self._container._get_scoped_context_var(  # type: ignore[reportPrivateUsage]
                scope
            )

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

    def _get_override_for(self, interface: Any) -> Any:
        """Hook for checking if an interface has an override."""
        return self._override_instances.get(interface, NOT_SET)

    def _wrap_for_override(self, annotation: Any, value: Any) -> Any:
        """Hook for wrapping dependencies to enable override patching."""
        return InstanceProxy(value, interface=annotation)

    def _post_resolve_override(self, interface: Any, instance: Any) -> Any:  # noqa: C901
        """Hook for patching resolved instances to support override."""
        if interface in self._override_instances:
            return self._override_instances[interface]

        if not hasattr(instance, "__dict__") or hasattr(
            instance, "__resolver_getter__"
        ):
            return instance

        wrapped = {
            name: value.interface
            for name, value in instance.__dict__.items()
            if isinstance(value, InstanceProxy)
        }

        def __resolver_getter__(name: str) -> Any:
            if name in wrapped:
                _interface = wrapped[name]
                # Resolve the dependency if it's wrapped
                return self._container.resolve(_interface)
            raise LookupError

        # Attach the resolver getter to the instance
        instance.__resolver_getter__ = __resolver_getter__

        if not hasattr(instance.__class__, "__getattribute_patched__"):

            def __getattribute__(_self: Any, name: str) -> Any:
                # Skip the resolver getter
                if name in {"__resolver_getter__", "__class__"}:
                    return object.__getattribute__(_self, name)

                if hasattr(_self, "__resolver_getter__"):
                    try:
                        return _self.__resolver_getter__(name)
                    except LookupError:
                        pass

                # Fall back to default behavior
                return object.__getattribute__(_self, name)

            # Apply the patched resolver if wrapped attributes exist
            instance.__class__.__getattribute__ = __getattribute__
            instance.__class__.__getattribute_patched__ = True

        return instance
