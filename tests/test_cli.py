"""Tests for the AnyDI CLI module."""

from unittest import mock

import pytest

from anydi import Container
from anydi._cli import main


class TestCLIMain:
    """Tests for the CLI main function."""

    def test_main_calls_graph_with_correct_arguments(self) -> None:
        """Test that main passes correct arguments to container.graph."""
        container = Container()
        container.graph = mock.MagicMock(return_value="graph output")

        with (
            mock.patch(
                "sys.argv",
                [
                    "anydi",
                    "mymodule:container",
                    "-o",
                    "mermaid",
                    "--full-path",
                    "--indent",
                    "4",
                ],
            ),
            mock.patch("anydi._cli.import_container", return_value=container),
        ):
            main()

        container.graph.assert_called_once_with(
            output_format="mermaid",
            full_path=True,
            ident=4,
        )

    def test_main_default_arguments(self) -> None:
        """Test that main uses correct default arguments."""
        container = Container()
        container.graph = mock.MagicMock(return_value="graph output")

        with (
            mock.patch("sys.argv", ["anydi", "mymodule:container"]),
            mock.patch("anydi._cli.import_container", return_value=container),
        ):
            main()

        container.graph.assert_called_once_with(
            output_format="tree",
            full_path=False,
            ident=2,
        )

    def test_main_with_scan_option(self) -> None:
        """Test main with --scan option."""
        container = Container()
        container.scan = mock.MagicMock()
        container.graph = mock.MagicMock(return_value="")

        with (
            mock.patch(
                "sys.argv", ["anydi", "mymodule:container", "--scan", "mypackage"]
            ),
            mock.patch("anydi._cli.import_container", return_value=container),
        ):
            main()

        container.scan.assert_called_once_with(["mypackage"])

    def test_main_with_multiple_scan_packages(self) -> None:
        """Test main with --scan option with multiple packages."""
        container = Container()
        container.scan = mock.MagicMock()
        container.graph = mock.MagicMock(return_value="")

        with (
            mock.patch(
                "sys.argv",
                [
                    "anydi",
                    "mymodule:container",
                    "-s",
                    "package1",
                    "package2",
                    "package3",
                ],
            ),
            mock.patch("anydi._cli.import_container", return_value=container),
        ):
            main()

        container.scan.assert_called_once_with(["package1", "package2", "package3"])

    def test_main_with_invalid_container_path_import_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test main exits with error when container import fails."""
        with (
            mock.patch("sys.argv", ["anydi", "invalid.module:container"]),
            mock.patch(
                "anydi._cli.import_container",
                side_effect=ImportError("Module not found"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "Module not found" in captured.err

    def test_main_with_invalid_container_path_value_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test main exits with error when container path is invalid."""
        with (
            mock.patch("sys.argv", ["anydi", "invalid"]),
            mock.patch(
                "anydi._cli.import_container",
                side_effect=ValueError("Invalid path"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err

    def test_main_with_scan_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main exits with error when scan fails."""
        container = Container()
        container.scan = mock.MagicMock(side_effect=Exception("Failed to scan package"))

        with (
            mock.patch(
                "sys.argv", ["anydi", "mymodule:container", "--scan", "badpackage"]
            ),
            mock.patch("anydi._cli.import_container", return_value=container),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error scanning packages:" in captured.err
        assert "Failed to scan package" in captured.err

    def test_main_with_graph_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test main exits with error when graph/build fails."""
        container = Container()
        container.graph = mock.MagicMock(
            side_effect=LookupError("Missing dependency `db`")
        )

        with (
            mock.patch("sys.argv", ["anydi", "mymodule:container"]),
            mock.patch("anydi._cli.import_container", return_value=container),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "Missing dependency" in captured.err
