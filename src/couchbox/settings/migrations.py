"""Settings file migrations: MIGRATIONS[n] turns version n values into version n+1.

Add one whenever a key is renamed or its meaning changes, with a test in
tests/unit/test_settings.py. Version 1 is the first public schema, so there are none yet.
"""

from collections.abc import Callable
from typing import Any

MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}
