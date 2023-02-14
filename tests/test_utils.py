from pyxdi._utils import scan_package  # noqa


def test_scan_package() -> None:
    scan_package("tests.scan.a.a2", include=["dep"])

    from tests.scan import result

    assert result == {"a", "a21", "a2", "a21:dep"}
