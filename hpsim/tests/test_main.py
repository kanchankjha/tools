"""Unit tests for __main__ module execution."""

import subprocess
import sys
from unittest.mock import patch, MagicMock


def test_main_module_execution():
    """Test __main__ module can be executed directly."""
    with patch("hpsim.cli.main") as mock_main:
        mock_main.return_value = 0

        # Import __main__ to trigger its code
        import hpsim.__main__

        # The module imports main, but doesn't call it unless run directly
        # This at least tests the import works
        assert hasattr(hpsim.__main__, "main")


def test_main_module_help():
    """Test __main__ module displays help."""
    result = subprocess.run(
        [sys.executable, "-m", "hpsim", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert "hpsim" in result.stdout
    assert "interface" in result.stdout


def test_main_module_missing_required_args():
    """Test __main__ module fails without required arguments."""
    result = subprocess.run(
        [sys.executable, "-m", "hpsim"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    # Should exit with error code
    assert result.returncode != 0


def test_cli_script_execution():
    """Test cli.py can be executed as a script."""
    result = subprocess.run(
        [sys.executable, "-m", "hpsim.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert "interface" in result.stdout
