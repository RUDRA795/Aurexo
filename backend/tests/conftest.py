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

from orca.agents.persistence import enforce_strict_msgpack_security
enforce_strict_msgpack_security(fail_fast=False)
