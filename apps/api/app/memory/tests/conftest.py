"""Shared fixtures for the memory test suite (Slice 8d).

Enforces the Tier 1 contract — the default suite is FREE and makes ZERO network calls —
with an autouse socket guard, and provides a TestClient bound to the offline LocalStore
backend. Tests marked ``cognee`` (Tier 2) opt out of the guard because they legitimately
talk to cognee + OpenAI.
"""

import socket

import pytest


@pytest.fixture(autouse=True)
def _no_network(request, monkeypatch):
    """Block outbound network for Tier 1 tests, so a green run *proves* $0 / no calls.

    ``cognee``-marked (Tier 2) tests are exempt — they need the real network. FastAPI's
    TestClient uses an in-process ASGI transport and SQLite is file-based, so neither
    resolves DNS nor opens an outbound socket; only a real external call trips this.
    """
    if request.node.get_closest_marker("cognee"):
        return  # Tier 2: allow real network.

    def _blocked(*args, **kwargs):
        raise RuntimeError(
            "Network access is disabled in the default (Tier 1) test suite. A test tried "
            "to open an outbound connection; mark it `cognee` if it legitimately must."
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


@pytest.fixture()
def client(monkeypatch):
    """A TestClient bound to a fresh, offline LocalStore backend (one per test)."""
    monkeypatch.setenv("MEMORY_BACKEND", "local")

    from app.main import app
    from app.memory.store import reset_store

    reset_store()  # rebuild the singleton from the (local) env for this test
    from fastapi.testclient import TestClient

    client = TestClient(app)
    yield client
    reset_store()
