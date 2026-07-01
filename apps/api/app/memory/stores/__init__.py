"""Concrete MemoryStore backends.

``local_store`` is offline (no cognee). ``graph_store`` and ``blob_store`` (added
in later slices) are the ONLY modules permitted to import ``cognee`` (guardrail #1).
"""
