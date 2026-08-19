import os
import threading
import time
from typing import Any

from dotenv import load_dotenv
from surrealdb import RecordID, Surreal

from benchmark.adapters.base import DatabaseAdapter
from benchmark.loader import (
    CLEAR_BATCH,
    COUNT_ALL_NODES,
    COUNT_NODES,
    COUNT_RELATIONSHIPS,
    CREATE_USER_INDEX,
    CREATE_USER_INDEX_SURREAL,
    LOAD_NODES,
    LOAD_RELATIONSHIPS,
)
from benchmark.workloads import (
    AGGREGATION,
    INDEXED_LOOKUP,
    POINT_LOOKUP,
    TRAVERSAL_1_HOP,
    TRAVERSAL_2_HOP,
    TRAVERSAL_3_HOP,
    WRITE_TICK,
)

load_dotenv()

RELATION_CHUNK = 50
NODE_CHUNK = 100
RETRY_ATTEMPTS = 5


def _norm(query: str) -> str:
    return " ".join(query.split())


def _http_url(url: str) -> str:
    if url.startswith("wss://"):
        return "https://" + url[len("wss://") :]
    if url.startswith("ws://"):
        return "http://" + url[len("ws://") :]
    return url


def _finish(result):
    if hasattr(result, "execute"):
        return result.execute()
    if hasattr(result, "first"):
        return result.first()
    return result


def _first_number(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        return _first_number(value[0]) if value else None
    if isinstance(value, dict):
        if "count" in value:
            return value["count"]
        return _first_number(next(iter(value.values()), None))
    return None


def _is_disconnect(exc: BaseException) -> bool:
    text = str(exc).lower()
    name = type(exc).__name__.lower()
    markers = (
        "keepalive",
        "timed out",
        "timeout",
        "connection closed",
        "connectionunavailable",
        "1011",
        "1006",
        "going away",
    )
    return any(marker in text or marker in name for marker in markers)


class SurrealDBCloudAdapter(DatabaseAdapter):
    def __init__(self) -> None:
        self.name = "SurrealDB Cloud"
        self.url = _http_url(os.getenv("SURREAL_URL") or "")
        self.namespace = os.getenv("SURREAL_NAMESPACE", "benchmark")
        self.database = os.getenv("SURREAL_DATABASE", "wikivote")
        self.username = os.getenv("SURREAL_USERNAME")
        self.password = os.getenv("SURREAL_PASSWORD")
        self.db = None
        self._local = threading.local()
        self._handlers = {
            _norm(LOAD_NODES): self._load_nodes,
            _norm(LOAD_RELATIONSHIPS): self._load_relationships,
            _norm(CLEAR_BATCH): self._clear,
            _norm(COUNT_ALL_NODES): self._count_users,
            _norm(COUNT_NODES): self._count_users,
            _norm(COUNT_RELATIONSHIPS): self._count_votes,
            _norm(CREATE_USER_INDEX): self._define_index,
            _norm(CREATE_USER_INDEX_SURREAL): self._define_index,
            _norm(POINT_LOOKUP): self._point_lookup,
            _norm(INDEXED_LOOKUP): self._indexed_lookup,
            _norm(TRAVERSAL_1_HOP): self._hop(1),
            _norm(TRAVERSAL_2_HOP): self._hop(2),
            _norm(TRAVERSAL_3_HOP): self._hop(3),
            _norm(AGGREGATION): self._aggregation,
            _norm(WRITE_TICK): self._write_tick,
        }

        if not self.url:
            raise ValueError("SurrealDB Cloud URL is not set.")

        if not self.username:
            raise ValueError("SurrealDB Cloud username is not set.")

        if not self.password:
            raise ValueError("SurrealDB Cloud password is not set.")

    def connect(self) -> None:
        self.db = self._open()
        self._local.db = self.db
        self._run(
            """
            DEFINE TABLE IF NOT EXISTS user SCHEMALESS;
            DEFINE TABLE IF NOT EXISTS voted TYPE RELATION IN user OUT user;
            """
        )

    def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        self._dispatch(query, params or {})

    def execute_value(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ):
        return self._dispatch(query, params or {})

    def close(self) -> None:
        local_db = getattr(self._local, "db", None)
        if local_db is not None:
            try:
                local_db.close()
            except Exception:
                pass
            self._local.db = None

        if self.db is not None and self.db is not local_db:
            try:
                self.db.close()
            except Exception:
                pass

        self.db = None

    def _reset_client(self) -> None:
        db = getattr(self._local, "db", None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
            self._local.db = None

        if self.db is db:
            self.db = None

    def _retry(self, fn):
        last: BaseException | None = None

        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                return fn()
            except Exception as exc:
                last = exc
                if not _is_disconnect(exc) or attempt == RETRY_ATTEMPTS:
                    raise
                print(
                    f"  {self.name} dropped during load, "
                    f"reconnect {attempt}/{RETRY_ATTEMPTS - 1}..."
                )
                self._reset_client()
                time.sleep(1.5 * attempt)

        raise last

    def _open(self):
        db = Surreal(self.url)
        connect = getattr(db, "connect", None)
        if callable(connect):
            connect()
        db.signin({"username": self.username, "password": self.password})
        db.use(self.namespace, self.database)
        return db

    def _client(self):
        db = getattr(self._local, "db", None)
        if db is None:
            db = self._open()
            self._local.db = db
        return db

    def _run(self, sql: str, params: dict[str, Any] | None = None):
        return self._retry(
            lambda: _finish(self._client().query(sql, params or {}))
        )

    def _dispatch(self, query: str, params: dict[str, Any]):
        handler = self._handlers.get(_norm(query))
        if handler is None:
            raise ValueError(
                "SurrealDB adapter has no mapping for this Cypher query."
            )
        return handler(params)

    def _user(self, node_id: str) -> RecordID:
        return RecordID("user", node_id)

    def _load_nodes(self, params: dict[str, Any]):
        rows = [
            {"id": self._user(row["id"]), "wiki_id": row["id"]}
            for row in params["rows"]
        ]
        last = None
        for start in range(0, len(rows), NODE_CHUNK):
            chunk = rows[start : start + NODE_CHUNK]
            last = self._retry(
                lambda current=chunk: _finish(self._client().insert("user", current))
            )
        return last

    def _load_relationships(self, params: dict[str, Any]):
        rows = [
            {
                "in": self._user(row["source"]),
                "out": self._user(row["target"]),
            }
            for row in params["rows"]
        ]
        last = None
        for start in range(0, len(rows), RELATION_CHUNK):
            chunk = rows[start : start + RELATION_CHUNK]
            last = self._retry(
                lambda current=chunk: _finish(
                    self._client().insert_relation("voted", current)
                )
            )
        return last

    def _clear(self, _params: dict[str, Any]):
        self._run("DELETE voted; DELETE user;")
        return 0

    def _count_users(self, _params: dict[str, Any]):
        return _first_number(self._run("SELECT count() FROM user GROUP ALL")) or 0

    def _count_votes(self, _params: dict[str, Any]):
        return _first_number(self._run("SELECT count() FROM voted GROUP ALL")) or 0

    def _define_index(self, _params: dict[str, Any]):
        return self._run(CREATE_USER_INDEX_SURREAL)

    def _point_lookup(self, params: dict[str, Any]):
        return self._run(
            "SELECT * FROM $start",
            {"start": self._user(params["id"])},
        )

    def _indexed_lookup(self, params: dict[str, Any]):
        return self._run(
            "SELECT * FROM user WHERE wiki_id = $id",
            {"id": params["id"]},
        )

    def _hop(self, depth: int):
        path = "->voted->user" * depth

        def run(params: dict[str, Any]):
            return self._run(
                f"SELECT count() FROM $start{path} GROUP ALL",
                {"start": self._user(params["id"])},
            )

        return run

    def _aggregation(self, _params: dict[str, Any]):
        return self._run(
            """
            SELECT wiki_id, count(->voted) AS votes
            FROM user
            ORDER BY votes DESC
            LIMIT 100
            """
        )

    def _write_tick(self, params: dict[str, Any]):
        return self._run(
            "UPDATE $start SET benchmark_mark = $mark",
            {
                "start": self._user(params["id"]),
                "mark": params["mark"],
            },
        )
