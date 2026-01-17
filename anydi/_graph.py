"""Graph generation for AnyDI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from ._provider import Provider

if TYPE_CHECKING:
    from ._container import Container


class Graph:
    """Graph generator for the dependency container."""

    def __init__(self, container: Container) -> None:
        self._container = container

    def draw(
        self,
        output_format: Literal["plain", "mermaid"] = "plain",
        *,
        full_path: bool = False,
    ) -> str:
        """Draw the dependency graph."""
        if output_format == "mermaid":
            return self._mermaid(full_path=full_path)
        return self._tree(full_path=full_path)

    def _mermaid(self, full_path: bool) -> str:
        """Generate mermaid format dependency graph."""
        lines: list[str] = ["graph TD"]
        seen_nodes: set[str] = set()

        for provider in self._container.providers.values():
            provider_name = self._get_name(provider.name, full_path)
            scope_label = self._get_scope_label(provider.scope, provider.from_context)
            node_id = provider_name.replace(".", "_")

            if node_id not in seen_nodes:
                seen_nodes.add(node_id)

            for param in provider.parameters:
                if param.provider is None:
                    continue

                dep_name = self._get_name(param.provider.name, full_path)
                dep_scope = self._get_scope_label(
                    param.provider.scope, param.provider.from_context
                )
                dep_node_id = dep_name.replace(".", "_")

                if dep_node_id not in seen_nodes:
                    seen_nodes.add(dep_node_id)

                # Use dashed line for from_context dependencies
                if param.provider.from_context:
                    arrow = "-.->"
                else:
                    arrow = "-->"

                lines.append(
                    f'    {node_id}["{provider_name} ({scope_label})"] '
                    f"{arrow}|{param.name}| "
                    f'{dep_node_id}["{dep_name} ({dep_scope})"]'
                )

        return "\n".join(lines)

    def _tree(self, full_path: bool) -> str:
        """Generate tree format dependency graph."""
        lines: list[str] = []

        # Find root providers (providers that are not dependencies of others)
        all_deps: set[Any] = set()
        for provider in self._container.providers.values():
            for param in provider.parameters:
                if param.provider is not None:
                    all_deps.add(param.provider.dependency_type)

        root_providers = [
            p
            for p in self._container.providers.values()
            if p.dependency_type not in all_deps and p.parameters
        ]

        for i, provider in enumerate(root_providers):
            if i > 0:
                lines.append("")
            lines.append(self._format_tree_node(provider, full_path))
            self._render_tree_children(provider, "", set(), lines, full_path)

        return "\n".join(lines)

    @staticmethod
    def _format_tree_node(
        provider: Provider, full_path: bool, param_name: str | None = None
    ) -> str:
        name = Graph._get_name(provider.name, full_path)
        scope_label = Graph._get_scope_label(provider.scope, provider.from_context)
        context_marker = " [context]" if provider.from_context else ""
        if param_name:
            return f"{param_name}: {name} ({scope_label}){context_marker}"
        return f"{name} ({scope_label}){context_marker}"

    @staticmethod
    def _render_tree_children(
        provider: Provider,
        prefix: str,
        visited: set[Any],
        lines: list[str],
        full_path: bool,
    ) -> None:
        if provider.dependency_type in visited:
            return
        visited = visited | {provider.dependency_type}

        deps = [p for p in provider.parameters if p.provider is not None]
        for i, param in enumerate(deps):
            dep_provider = param.provider
            if dep_provider is None:
                continue
            is_last = i == len(deps) - 1
            connector = "└── " if is_last else "├── "
            node_text = Graph._format_tree_node(dep_provider, full_path, param.name)
            lines.append(f"{prefix}{connector}{node_text}")
            extension = "    " if is_last else "│   "
            Graph._render_tree_children(
                dep_provider, prefix + extension, visited, lines, full_path
            )

    @staticmethod
    def _get_name(name: str, full_path: bool) -> str:
        if full_path:
            return name
        return name.rsplit(".", 1)[-1]

    @staticmethod
    def _get_scope_label(scope: str, from_context: bool) -> str:
        if from_context:
            return f"{scope}/context"
        return scope
