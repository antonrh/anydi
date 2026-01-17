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
