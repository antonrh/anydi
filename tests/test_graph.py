"""Tests for the graph method."""

from anydi import Container


class GraphDatabase:
    pass


class GraphCache:
    pass


class GraphRepository:
    def __init__(self, db: GraphDatabase) -> None:
        self.db = db


class GraphCachedRepository:
    def __init__(self, db: GraphDatabase, cache: GraphCache) -> None:
        self.db = db
        self.cache = cache


class GraphService:
    def __init__(self, repo: GraphRepository) -> None:
        self.repo = repo


class GraphServiceWithMultipleDeps:
    def __init__(
        self, repo: GraphRepository, cache: GraphCache, db: GraphDatabase
    ) -> None:
        self.repo = repo
        self.cache = cache
        self.db = db


class GraphController:
    def __init__(self, service: GraphService, cache: GraphCache) -> None:
        self.service = service
        self.cache = cache


class GraphCurrentUser:
    pass


class TestContainerGraph:
    """Tests for the graph method."""

    def test_graph_tree_format(self) -> None:
        """Test graph output in tree format (default)."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphRepository, scope="singleton")
        container.register(GraphService, scope="singleton")

        result = container.graph()

        assert result == (
            "GraphService (singleton)\n"
            "└── repo: GraphRepository (singleton)\n"
            "    └── db: GraphDatabase (singleton)"
        )

    def test_graph_tree_multiple_deps(self) -> None:
        """Test tree format with multiple dependencies."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphCache, scope="singleton")
        container.register(GraphCachedRepository, scope="singleton")

        result = container.graph()

        assert result == (
            "GraphCachedRepository (singleton)\n"
            "├── db: GraphDatabase (singleton)\n"
            "└── cache: GraphCache (singleton)"
        )

    def test_graph_tree_deep_hierarchy(self) -> None:
        """Test tree format with deep hierarchy."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphCache, scope="singleton")
        container.register(GraphRepository, scope="singleton")
        container.register(GraphService, scope="singleton")
        container.register(GraphController, scope="singleton")

        result = container.graph()

        assert result == (
            "GraphController (singleton)\n"
            "├── service: GraphService (singleton)\n"
            "│   └── repo: GraphRepository (singleton)\n"
            "│       └── db: GraphDatabase (singleton)\n"
            "└── cache: GraphCache (singleton)"
        )

    def test_graph_tree_with_scopes(self) -> None:
        """Test tree format shows different scopes."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphCache, scope="transient")
        container.register(GraphCachedRepository, scope="transient")

        result = container.graph()

        assert result == (
            "GraphCachedRepository (transient)\n"
            "├── db: GraphDatabase (singleton)\n"
            "└── cache: GraphCache (transient)"
        )

    def test_graph_tree_with_context(self) -> None:
        """Test tree format shows context providers."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphCurrentUser, scope="request", from_context=True)

        class LocalRequestService:
            def __init__(self, db: GraphDatabase, user: GraphCurrentUser) -> None:
                self.db = db
                self.user = user

        container.register(LocalRequestService, scope="request")

        result = container.graph()

        assert result == (
            "LocalRequestService (request)\n"
            "├── db: GraphDatabase (singleton)\n"
            "└── user: GraphCurrentUser (request/context) [context]"
        )

    def test_graph_mermaid_format(self) -> None:
        """Test graph output in mermaid format."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphRepository, scope="singleton")
        container.register(GraphService, scope="singleton")

        result = container.graph(output_format="mermaid")

        assert result == (
            "graph TD\n"
            '    GraphRepository["GraphRepository (singleton)"] '
            '-->|db| GraphDatabase["GraphDatabase (singleton)"]\n'
            '    GraphService["GraphService (singleton)"] '
            '-->|repo| GraphRepository["GraphRepository (singleton)"]'
        )

    def test_graph_mermaid_with_context(self) -> None:
        """Test mermaid format shows dashed lines for context deps."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphCurrentUser, scope="request", from_context=True)

        class LocalRequestService:
            def __init__(self, db: GraphDatabase, user: GraphCurrentUser) -> None:
                self.db = db
                self.user = user

        container.register(LocalRequestService, scope="request")

        result = container.graph(output_format="mermaid")

        assert "-.->|user|" in result
        assert "-->|db|" in result

    def test_graph_auto_builds(self) -> None:
        """Test that graph calls build if not already built."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")

        assert container.ready is False

        container.graph()

        assert container.ready is True

    def test_graph_empty_container(self) -> None:
        """Test graph with no dependencies."""
        container = Container()

        result = container.graph()

        assert result == ""

    def test_graph_mermaid_empty(self) -> None:
        """Test mermaid graph with no dependencies."""
        container = Container()

        result = container.graph(output_format="mermaid")

        assert result == "graph TD"

    def test_graph_full_path(self) -> None:
        """Test graph with full module path."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphRepository, scope="singleton")

        result = container.graph(full_path=True)

        assert "tests.test_graph.GraphRepository (singleton)" in result
        assert "tests.test_graph.GraphDatabase (singleton)" in result

    def test_graph_dot_format(self) -> None:
        """Test graph output in DOT format."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphRepository, scope="singleton")
        container.register(GraphService, scope="singleton")

        result = container.graph(output_format="dot")

        assert "digraph G {" in result
        assert "node [shape=box];" in result
        assert (
            '"GraphRepository (singleton)" -> "GraphDatabase (singleton)" [label="db"];'
        ) in result
        assert (
            '"GraphService (singleton)" -> "GraphRepository (singleton)" '
            '[label="repo"];'
        ) in result
        assert result.endswith("}")

    def test_graph_dot_with_context(self) -> None:
        """Test DOT format shows dashed lines for context deps."""
        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphCurrentUser, scope="request", from_context=True)

        class LocalRequestService:
            def __init__(self, db: GraphDatabase, user: GraphCurrentUser) -> None:
                self.db = db
                self.user = user

        container.register(LocalRequestService, scope="request")

        result = container.graph(output_format="dot")

        assert "[style=dashed]" in result
        assert '[label="user"]' in result
        assert '[label="db"]' in result

    def test_graph_dot_empty(self) -> None:
        """Test DOT graph with no dependencies."""
        container = Container()

        result = container.graph(output_format="dot")

        assert result == "digraph G {\n    node [shape=box];\n}"

    def test_graph_json_format(self) -> None:
        """Test graph output in JSON format."""
        import json

        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphRepository, scope="singleton")

        result = container.graph(output_format="json")
        data = json.loads(result)

        assert "providers" in data
        assert len(data["providers"]) == 2

        # Find providers by type
        providers_by_type = {p["type"]: p for p in data["providers"]}

        assert "GraphDatabase" in providers_by_type
        assert providers_by_type["GraphDatabase"]["scope"] == "singleton"
        assert providers_by_type["GraphDatabase"]["dependencies"] == []

        assert "GraphRepository" in providers_by_type
        assert providers_by_type["GraphRepository"]["scope"] == "singleton"
        assert providers_by_type["GraphRepository"]["dependencies"] == [
            {"name": "db", "type": "GraphDatabase"}
        ]

    def test_graph_json_with_context(self) -> None:
        """Test JSON format includes from_context flag."""
        import json

        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphCurrentUser, scope="request", from_context=True)

        result = container.graph(output_format="json")
        data = json.loads(result)

        providers_by_type = {p["type"]: p for p in data["providers"]}

        assert providers_by_type["GraphDatabase"]["from_context"] is False
        assert providers_by_type["GraphCurrentUser"]["from_context"] is True

    def test_graph_json_full_path(self) -> None:
        """Test JSON format with full module path."""
        import json

        container = Container()
        container.register(GraphDatabase, scope="singleton")
        container.register(GraphRepository, scope="singleton")

        result = container.graph(output_format="json", full_path=True)
        data = json.loads(result)

        providers_by_type = {p["type"]: p for p in data["providers"]}

        assert "tests.test_graph.GraphDatabase" in providers_by_type
        assert "tests.test_graph.GraphRepository" in providers_by_type
        assert providers_by_type["tests.test_graph.GraphRepository"][
            "dependencies"
        ] == [{"name": "db", "type": "tests.test_graph.GraphDatabase"}]

    def test_graph_json_empty(self) -> None:
        """Test JSON graph with no dependencies."""
        import json

        container = Container()

        result = container.graph(output_format="json")
        data = json.loads(result)

        assert data == {"providers": []}

    def test_graph_with_aliases(self) -> None:
        """Test graph formats correctly show aliases."""
        import json

        class IDatabase:
            pass

        class DatabaseImpl(IDatabase):
            pass

        container = Container()
        container.register(DatabaseImpl, scope="singleton")
        container.alias(IDatabase, DatabaseImpl)

        # Test tree format with alias
        tree_result = container.graph(output_format="tree")
        assert "[alias: IDatabase]" in tree_result

        # Test JSON format with alias
        json_result = container.graph(output_format="json")
        data = json.loads(json_result)

        providers_by_type = {p["type"]: p for p in data["providers"]}
        assert "DatabaseImpl" in providers_by_type
        assert providers_by_type["DatabaseImpl"]["aliases"] == ["IDatabase"]

    def test_graph_tree_shared_dependencies(self) -> None:
        """Test tree format doesn't repeat shared dependencies (cycle prevention)."""

        class SharedDep:
            pass

        class ServiceA:
            def __init__(self, shared: SharedDep) -> None:
                self.shared = shared

        class ServiceB:
            def __init__(self, shared: SharedDep) -> None:
                self.shared = shared

        class Controller:
            def __init__(self, a: ServiceA, b: ServiceB) -> None:
                self.a = a
                self.b = b

        container = Container()
        container.register(SharedDep, scope="singleton")
        container.register(ServiceA, scope="singleton")
        container.register(ServiceB, scope="singleton")
        container.register(Controller, scope="singleton")

        result = container.graph(output_format="tree")

        # The tree should show shared dep under both services
        assert "SharedDep" in result
        assert "ServiceA" in result
        assert "ServiceB" in result
        assert "Controller" in result
