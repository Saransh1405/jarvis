"""Pytest configuration — force stub LLM so API tests need no API keys."""

import os

os.environ.setdefault("LLM_PROVIDER", "stub")
os.environ.setdefault("LLM_MODEL", "stub-model")
