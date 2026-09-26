import asyncio
import os
import sys
import pytest

# Ensure tests on Windows use WindowsSelectorEventLoopPolicy for async psycopg3 compatibility
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Ensure tests on Windows do not leave socket connections across closed loops
os.environ["ORCA_DB_POOL"] = "nullpool"
os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"

try:
    from orca.agents.persistence import enforce_strict_msgpack_security
    enforce_strict_msgpack_security(fail_fast=False)
except ImportError:
    pass

import socket

def is_db_reachable(host="127.0.0.1", port=5432) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except (OSError, ConnectionRefusedError):
        return False

_DB_AVAILABLE = is_db_reachable()

def pytest_collection_modifyitems(config, items):
    if not _DB_AVAILABLE:
        skip_db = pytest.mark.skip(reason="PostgreSQL/PostGIS is offline on port 5432 (start Docker Desktop to run live DB tests)")
        db_test_modules = {
            "test_cache_fallback.py",
            "test_pfz_repository.py",
            "test_postgis_spatial.py",
            "test_pgvector.py",
            "test_graph_persistence.py",
            "test_hybrid_rag.py",
            "test_advisory_rag.py",
        }
        for item in items:
            if any(mod in str(item.fspath) for mod in db_test_modules):
                item.add_marker(skip_db)

