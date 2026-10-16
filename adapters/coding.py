"""Coding-session adapter. Recorded logs are already normalized JSONL for now.
Event kinds: file_open, edit, test_fail, test_pass, inspect_error, idle."""
from adapters.base import load_jsonl

__all__ = ["load_jsonl"]
