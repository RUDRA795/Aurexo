from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
import os
import re
import sys
from typing import Any, AsyncGenerator, Sequence

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
import psycopg
from psycopg.rows import dict_row

from orca.database.session import get_raw_database_url

logger = logging.getLogger(__name__)

# Valid namespaces for durable application memory in AsyncPostgresStore
VALID_STORE_PREFIXES = frozenset({"users", "regions", "investigations"})


def configure_windows_event_loop_policy() -> None:
    """Configure WindowsSelectorEventLoopPolicy on Windows for async psycopg compatibility.

    Must only be called during application startup before the event loop starts running.
    """
    if sys.platform == "win32":
        try:
            loop = asyncio.get_running_loop()
            logger.debug("Event loop already running; skipping policy mutation: %s", loop)
        except RuntimeError:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            logger.info("Configured WindowsSelectorEventLoopPolicy for async psycopg.")


def enforce_strict_msgpack_security(*, fail_fast: bool = True) -> bool:
    """Enforce strict MessagePack deserialization settings.

    In production-like environments or when fail_fast=True, verifies that strict mode
    is active and disallows arbitrary deserialization.
    """
    os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"

    try:
        import langgraph.checkpoint.serde._msgpack as mp

        # Explicitly register safe ORCA domain models and enums into SAFE_MSGPACK_TYPES
        orca_safe = {
            # orca_contract models and enums
            ("orca.schemas.orca_contract", "Geometry"),
            ("orca.schemas.orca_contract", "Evidence"),
            ("orca.schemas.orca_contract", "SourceMetadata"),
            ("orca.schemas.orca_contract", "SourceScore"),
            ("orca.schemas.orca_contract", "TimeWindow"),
            ("orca.schemas.orca_contract", "VerificationResult"),
            ("orca.schemas.orca_contract", "VerificationCheck"),
            ("orca.schemas.orca_contract", "VerificationSeverity"),
            ("orca.schemas.orca_contract", "FinalResponse"),
            ("orca.schemas.orca_contract", "MapOverlay"),
            ("orca.schemas.orca_contract", "SafetyDecision"),
            ("orca.schemas.orca_contract", "SafetyStatus"),
            ("orca.schemas.orca_contract", "ConflictRecord"),
            ("orca.schemas.orca_contract", "ResponseType"),
            ("orca.schemas.orca_contract", "AccessMethod"),
            ("orca.schemas.orca_contract", "EvidenceType"),
            ("orca.schemas.orca_contract", "DataQuality"),
            ("orca.schemas.orca_contract", "ToolName"),
            ("orca.schemas.orca_contract", "ToolStatus"),
            ("orca.schemas.orca_contract", "ToolCall"),
            ("orca.schemas.orca_contract", "ToolDefinition"),
            ("orca.schemas.orca_contract", "PlanStep"),
            # pfz_contract
            ("orca.schemas.pfz_contract", "PFZPoint"),
            ("orca.schemas.pfz_contract", "PFZQuery"),
            ("orca.schemas.pfz_contract", "PFZQueryResult"),
            ("orca.schemas.pfz_contract", "PFZAccessTier"),
            # agent_runtime
            ("orca.schemas.agent_runtime", "IntentEnum"),
            ("orca.schemas.agent_runtime", "PlanStep"),
            ("orca.schemas.agent_runtime", "TaskPlan"),
            ("orca.schemas.agent_runtime", "EvidenceRequirement"),
            ("orca.schemas.agent_runtime", "SufficiencyEvaluationResult"),
            ("orca.schemas.agent_runtime", "ClaimGrounding"),
            ("orca.schemas.agent_runtime", "AgentRuntimeResult"),
        }
        if hasattr(mp, "SAFE_MSGPACK_TYPES"):
            mp.SAFE_MSGPACK_TYPES = frozenset(mp.SAFE_MSGPACK_TYPES.union(orca_safe))

        is_strict = getattr(mp, "STRICT_MSGPACK_ENABLED", False) or os.getenv("LANGGRAPH_STRICT_MSGPACK") == "true"
        if not is_strict and fail_fast:
            raise RuntimeError(
                "Security violation: LANGGRAPH_STRICT_MSGPACK must be enabled in production environments."
            )
        return True
    except Exception as exc:
        if fail_fast:
            raise RuntimeError(f"Failed to enforce strict MsgPack security: {exc}") from exc
        logger.warning("Strict MsgPack check encountered error: %s", exc)
        return False


def validate_store_namespace(namespace: tuple[str, ...]) -> None:
    """Validate structure of store namespaces to prevent arbitrary or malicious prefixes."""
    if not namespace or len(namespace) < 2:
        raise ValueError(
            f"Store namespace must contain at least 2 components (e.g. ('users', 'u1', 'prefs')), got: {namespace}"
        )
    prefix = namespace[0].lower().strip()
    if prefix not in VALID_STORE_PREFIXES:
        raise ValueError(
            f"Invalid store namespace prefix '{prefix}'. Allowed prefixes: {sorted(VALID_STORE_PREFIXES)}"
        )
    for seg in namespace:
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", seg):
            raise ValueError(f"Invalid namespace segment '{seg}': must be alphanumeric/slug.")


class OrcaPersistenceManager:
    """Production persistence manager governing LangGraph PostgreSQL checkpointer,

    cross-thread Store, strict serialization, and checkpoint retention.
    """

    def __init__(self, conn_string: str | None = None) -> None:
        configure_windows_event_loop_policy()
        enforce_strict_msgpack_security(fail_fast=False)
        self.conn_string = conn_string or get_raw_database_url()

    async def setup(self) -> None:
        """Run official setup() procedures for both AsyncPostgresSaver and AsyncPostgresStore."""
        configure_windows_event_loop_policy()
        async with AsyncPostgresSaver.from_conn_string(self.conn_string) as checkpointer:
            await checkpointer.setup()
        async with AsyncPostgresStore.from_conn_string(self.conn_string) as store:
            await store.setup()
        logger.info("Official LangGraph PostgreSQL checkpointer and store schemas initialized.")

    @asynccontextmanager
    async def get_checkpointer(self) -> AsyncGenerator[AsyncPostgresSaver, None]:
        """Yield an official AsyncPostgresSaver connected to the PostgreSQL database."""
        configure_windows_event_loop_policy()
        async with AsyncPostgresSaver.from_conn_string(self.conn_string) as checkpointer:
            yield checkpointer

    @asynccontextmanager
    async def get_store(self) -> AsyncGenerator[AsyncPostgresStore, None]:
        """Yield an official AsyncPostgresStore connected to the PostgreSQL database."""
        configure_windows_event_loop_policy()
        async with AsyncPostgresStore.from_conn_string(self.conn_string) as store:
            yield store

    # -----------------------------------------------------------------------
    # Checkpoint Retention & Maintenance
    # -----------------------------------------------------------------------
    async def list_thread_checkpoints(self, thread_id: str) -> list[dict[str, Any]]:
        """List checkpoints for a thread using official checkpointer API."""
        checkpoints: list[dict[str, Any]] = []
        async with self.get_checkpointer() as checkpointer:
            config = {"configurable": {"thread_id": thread_id}}
            async for cp_tuple in checkpointer.alist(config):
                checkpoints.append({
                    "checkpoint_id": cp_tuple.checkpoint["id"],
                    "checkpoint_ns": cp_tuple.config.get("configurable", {}).get("checkpoint_ns", ""),
                    "thread_id": thread_id,
                    "metadata": cp_tuple.metadata,
                    "parent_checkpoint_id": cp_tuple.parent_config.get("configurable", {}).get("checkpoint_id")
                    if cp_tuple.parent_config else None,
                })
        return checkpoints

    async def prune_thread_checkpoints(
        self,
        thread_id: str,
        keep_last_n: int = 15,
        protect_latest: bool = True,
    ) -> int:
        """Safely prune older checkpoints for a thread beyond keep_last_n.

        Adheres to non-negotiable retention invariants:
        - Never alters the official schema.
        - Never deletes the latest valid checkpoint.
        - Safely removes older records via an isolated transaction.
        """
        if keep_last_n < 1:
            raise ValueError(f"keep_last_n must be at least 1, got {keep_last_n}")

        all_cps = await self.list_thread_checkpoints(thread_id)
        if len(all_cps) <= keep_last_n:
            return 0

        # Most recent checkpoints first
        eligible_for_pruning = all_cps[keep_last_n:]
        prune_ids = [c["checkpoint_id"] for c in eligible_for_pruning]

        if not prune_ids:
            return 0

        # Isolated maintenance SQL against official schema
        configure_windows_event_loop_policy()
        async with await psycopg.AsyncConnection.connect(self.conn_string, autocommit=True) as conn:
            async with conn.cursor() as cur:
                # 1. Prune checkpoint writes associated with old checkpoints
                await cur.execute(
                    """
                    DELETE FROM checkpoint_writes
                    WHERE thread_id = %(tid)s
                      AND checkpoint_id = ANY(%(cids)s);
                    """,
                    {"tid": thread_id, "cids": prune_ids},
                )
                # 2. Prune old checkpoints
                await cur.execute(
                    """
                    DELETE FROM checkpoints
                    WHERE thread_id = %(tid)s
                      AND checkpoint_id = ANY(%(cids)s);
                    """,
                    {"tid": thread_id, "cids": prune_ids},
                )
                pruned_count = cur.rowcount

        logger.info(
            "Pruned %d older checkpoints for thread '%s' (retained %d).",
            pruned_count,
            thread_id,
            keep_last_n,
        )
        return pruned_count

    # -----------------------------------------------------------------------
    # Durable Application Memory (AsyncPostgresStore)
    # -----------------------------------------------------------------------
    async def put_memory(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Store durable cross-thread memory in official AsyncPostgresStore with namespace validation."""
        validate_store_namespace(namespace)
        if not key or not key.strip():
            raise ValueError("Store memory key cannot be empty.")

        async with self.get_store() as store:
            await store.aput(namespace, key.strip(), value)

    async def get_memory(
        self,
        namespace: tuple[str, ...],
        key: str,
    ) -> dict[str, Any] | None:
        """Retrieve durable memory from official AsyncPostgresStore."""
        validate_store_namespace(namespace)
        async with self.get_store() as store:
            item = await store.aget(namespace, key.strip())
            return item.value if item is not None else None

    async def search_memory(
        self,
        namespace_prefix: tuple[str, ...],
        query: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search durable memories within an approved namespace prefix."""
        if not namespace_prefix or namespace_prefix[0].lower().strip() not in VALID_STORE_PREFIXES:
            raise ValueError(f"Invalid namespace prefix: {namespace_prefix}")

        async with self.get_store() as store:
            items = await store.asearch(namespace_prefix, query=query, limit=limit)
            return [{"key": item.key, "namespace": item.namespace, "value": item.value} for item in items]

    # -----------------------------------------------------------------------
    # Multi-Turn Thread Execution & Inspection
    # -----------------------------------------------------------------------
    async def inspect_thread_state(self, thread_id: str) -> dict[str, Any] | None:
        """Inspect current checkpoint state and metadata directly from PostgreSQL checkpointer."""
        async with self.get_checkpointer() as checkpointer:
            config = {"configurable": {"thread_id": thread_id}}
            tuple_res = await checkpointer.aget_tuple(config)
            if tuple_res is None:
                return None
            return {
                "thread_id": thread_id,
                "checkpoint_id": tuple_res.checkpoint["id"],
                "checkpoint_ns": tuple_res.config.get("configurable", {}).get("checkpoint_ns", ""),
                "channel_values": tuple_res.checkpoint.get("channel_values", {}),
                "metadata": tuple_res.metadata,
                "parent_config": tuple_res.parent_config,
            }

    async def execute_thread_turn(
        self,
        graph: Any,
        query: str,
        thread_id: str,
        coordinates: Any = None,
        sector: str | None = None,
    ) -> dict[str, Any]:
        """Execute a conversation turn on the compiled LangGraph workflow with thread persistence."""
        config = {"configurable": {"thread_id": thread_id}}
        input_state: dict[str, Any] = {
            "user_query": query,
            "thread_id": thread_id,
        }
        if coordinates is not None:
            input_state["coordinates"] = coordinates
        if sector is not None:
            input_state["sector"] = sector

        return await graph.ainvoke(input_state, config=config)

    async def resume_thread(
        self,
        graph: Any,
        thread_id: str,
        resume_input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resume an interrupted graph execution on a specific thread."""
        config = {"configurable": {"thread_id": thread_id}}
        return await graph.ainvoke(resume_input, config=config)

