from pyxdi.scanner import injectable


def test_injectable_decorator_no_args() -> None:
    @injectable
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") is True
    assert getattr(my_func, "__injectable_tags__") is None


def test_injectable_decorator_no_args_provided() -> None:
    @injectable()
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") is True
    assert getattr(my_func, "__injectable_tags__") is None


def test_injectable_decorator() -> None:
    @injectable(tags=["tag1", "tag2"])
    def my_func() -> None:
        pass

    assert getattr(my_func, "__injectable__") is True
    assert getattr(my_func, "__injectable_tags__") == ["tag1", "tag2"]
