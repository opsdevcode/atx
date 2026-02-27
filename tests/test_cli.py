"""Tests for atx CLI."""

import pytest
from click.testing import CliRunner

from atx.cli import main


def test_cli_help():
    """CLI --help exits 0 and shows usage."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "atx" in result.output
    assert "atmos" in result.output
