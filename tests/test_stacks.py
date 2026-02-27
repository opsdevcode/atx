"""Tests for atx stack expansion and discovery."""

import pytest

from atx.stacks import expand_stack


def test_expand_stack_known_aliases():
    """Expand known stack aliases to full names."""
    assert expand_stack("dev") == "platform-use1-dev"
    assert expand_stack("sb") == "platform-use1-sandbox"
    assert expand_stack("sandbox") == "platform-use1-sandbox"
    assert expand_stack("stage") == "platform-use1-staging"
    assert expand_stack("staging") == "platform-use1-staging"
    assert expand_stack("prod") == "platform-use1-prod"
    assert expand_stack("production") == "platform-use1-prod"
    assert expand_stack("otto") == "core-use1-otto"


def test_expand_stack_unknown_returns_unchanged():
    """Unknown aliases are returned unchanged."""
    assert expand_stack("platform-use1-prod") == "platform-use1-prod"
    assert expand_stack("custom-stack") == "custom-stack"
