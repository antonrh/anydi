from anydi._context import InstanceContext


class TestInstanceContext:
    def test_setitem_and_getitem(self) -> None:
        context = InstanceContext()

        context[str] = "test_value"

        assert context[str] == "test_value"

        context[int] = 42

        assert context[int] == 42
        assert context[str] == "test_value"
