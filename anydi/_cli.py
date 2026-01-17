"""AnyDI CLI module."""

import argparse
import sys

from anydi import import_container


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="AnyDI CLI")
    parser.add_argument(
        "container",
        help="Path to the container instance or factory (e.g., 'module:container')",
    )
    parser.add_argument(
        "--output-format",
        "-o",
        choices=["plain", "mermaid", "dot", "json"],
        default="plain",
        help="Output format for the dependency graph",
    )
    parser.add_argument(
        "--full-path",
        action="store_true",
        help="Show full module path for dependencies",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation level",
    )

    args = parser.parse_args()

    try:
        container = import_container(args.container)
    except (ImportError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    graph_out = container.graph(
        output_format=args.output_format,
        full_path=args.full_path,
        ident=args.indent,
    )
    print(graph_out)  # noqa: T201


if __name__ == "__main__":
    main()
