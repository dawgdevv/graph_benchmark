import os
import re
from typing import Any

from dotenv import load_dotenv
from typedb.driver import (
    Credentials,
    DriverOptions,
    DriverTlsConfig,
    TransactionOptions,
    TransactionType,
    TypeDB,
)

from benchmark.adapters.base import DatabaseAdapter
from benchmark.loader import (
    CLEAR_BATCH,
    COUNT_ALL_NODES,
    COUNT_NODES,
    COUNT_RELATIONSHIPS,
    CREATE_USER_INDEX,
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

SCHEMA = """
define
  attribute user-id, value string;
  attribute benchmark-mark, value integer;
  entity user,
    owns user-id @key,
    owns benchmark-mark,
    plays voted:voter,
    plays voted:votee;
  relation voted,
    relates voter,
    relates votee;
"""

WRITE_TIMEOUT = TransactionOptions(transaction_timeout_millis=10 * 60 * 1000)
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
CHUNK = 50


def _norm(query: str) -> str:
    return " ".join(query.split())


def _id(value: Any) -> str:
    text = str(value)
    if not SAFE_ID.match(text):
        raise ValueError(f"Unsafe TypeDB id: {text!r}")
    return text


def _as_int(concept) -> int | None:
    if concept is None:
        return None
    if hasattr(concept, "try_get_integer"):
        value = concept.try_get_integer()
        if value is not None:
            return int(value)
    if hasattr(concept, "get_integer"):
        return int(concept.get_integer())
    return None


class TypeDBCloudAdapter(DatabaseAdapter):
    def __init__(self) -> None:
        self.name = "TypeDB Cloud"
        self.address = os.getenv("TYPEDB_ADDRESS")
        self.username = os.getenv("TYPEDB_USERNAME", "admin")
        self.password = os.getenv("TYPEDB_PASSWORD")
        self.database = os.getenv("TYPEDB_DATABASE", "wikivote")
        self.tls = os.getenv("TYPEDB_TLS", "true").lower() not in {
            "0",
            "false",
            "no",
        }
        self.driver = None
        self._handlers = {
            _norm(LOAD_NODES): self._load_nodes,
            _norm(LOAD_RELATIONSHIPS): self._load_relationships,
            _norm(CLEAR_BATCH): self._clear,
            _norm(COUNT_ALL_NODES): self._count_users,
            _norm(COUNT_NODES): self._count_users,
            _norm(COUNT_RELATIONSHIPS): self._count_votes,
            _norm(CREATE_USER_INDEX): self._define_schema,
            _norm(POINT_LOOKUP): self._point_lookup,
            _norm(INDEXED_LOOKUP): self._indexed_lookup,
            _norm(TRAVERSAL_1_HOP): self._hop(1),
            _norm(TRAVERSAL_2_HOP): self._hop(2),
            _norm(TRAVERSAL_3_HOP): self._hop(3),
            _norm(AGGREGATION): self._aggregation,
            _norm(WRITE_TICK): self._write_tick,
        }

        if not self.address:
            raise ValueError("TypeDB Cloud address is not set.")

        if not self.password:
            raise ValueError("TypeDB Cloud password is not set.")

    def connect(self) -> None:
        tls = (
            DriverTlsConfig.enabled_with_native_root_ca()
            if self.tls
            else DriverTlsConfig.disabled()
        )
        self.driver = TypeDB.driver(
            self.address,
            Credentials(self.username, self.password),
            DriverOptions(tls),
        )

        if not self.driver.databases.contains(self.database):
            self.driver.databases.create(self.database)

        self._define_schema({})

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
        if self.driver is not None:
            self.driver.close()
            self.driver = None

    def _dispatch(self, query: str, params: dict[str, Any]):
        if self.driver is None:
            raise RuntimeError(f"{self.name} connection is not open.")

        handler = self._handlers.get(_norm(query))
        if handler is None:
            raise ValueError("TypeDB adapter has no mapping for this Cypher query.")
        return handler(params)

    def _write(self, queries: list[str]) -> None:
        with self.driver.transaction(
            self.database,
            TransactionType.WRITE,
            options=WRITE_TIMEOUT,
        ) as tx:
            promises = [tx.query(query) for query in queries]
            for promise in promises:
                promise.resolve()
            tx.commit()

    def _read(self, query: str):
        with self.driver.transaction(self.database, TransactionType.READ) as tx:
            return tx.query(query).resolve()

    def _reduce_count(self, query: str) -> int:
        answer = self._read(query)
        for row in answer.as_concept_rows():
            value = _as_int(row.get("count"))
            if value is not None:
                return value
        return 0

    def _define_schema(self, _params: dict[str, Any]):
        try:
            with self.driver.transaction(
                self.database,
                TransactionType.SCHEMA,
                options=WRITE_TIMEOUT,
            ) as tx:
                tx.query(SCHEMA).resolve()
                tx.commit()
        except Exception as exc:
            text = str(exc).lower()
            if "already" in text or "exist" in text or "defined" in text:
                return
            raise

    def _load_nodes(self, params: dict[str, Any]):
        rows = params["rows"]
        for start in range(0, len(rows), CHUNK):
            chunk = rows[start : start + CHUNK]
            queries = [
                f'insert $u isa user, has user-id "{_id(row["id"])}";'
                for row in chunk
            ]
            self._write(queries)

    def _load_relationships(self, params: dict[str, Any]):
        rows = params["rows"]
        for start in range(0, len(rows), CHUNK):
            chunk = rows[start : start + CHUNK]
            queries = [
                f"""
                match
                  $s isa user, has user-id "{_id(row["source"])}";
                  $t isa user, has user-id "{_id(row["target"])}";
                insert
                  (voter: $s, votee: $t) isa voted;
                """
                for row in chunk
            ]
            self._write(queries)

    def _clear(self, _params: dict[str, Any]):
        self._write(
            [
                "match $r isa voted; delete $r;",
                "match $u isa user; delete $u;",
            ]
        )
        return 0

    def _count_users(self, _params: dict[str, Any]) -> int:
        return self._reduce_count("match $u isa user; reduce $count = count;")

    def _count_votes(self, _params: dict[str, Any]) -> int:
        return self._reduce_count("match $r isa voted; reduce $count = count;")

    def _point_lookup(self, params: dict[str, Any]):
        node_id = _id(params["id"])
        answer = self._read(
            f'match $u isa user, has user-id "{node_id}"; '
            'fetch { "id": $u.user-id };'
        )
        return list(answer.as_concept_documents())

    def _indexed_lookup(self, params: dict[str, Any]):
        node_id = _id(params["id"])
        answer = self._read(
            f'match $u isa user, has user-id $id; $id == "{node_id}"; '
            'fetch { "id": $id };'
        )
        return list(answer.as_concept_documents())

    def _hop(self, depth: int):
        hops = ["(voter: $n0, votee: $n1) isa voted;"]
        for index in range(1, depth):
            hops.append(
                f"(voter: $n{index}, votee: $n{index + 1}) isa voted;"
            )

        def run(params: dict[str, Any]):
            node_id = _id(params["id"])
            pattern = "\n  ".join(hops)
            return self._reduce_count(
                f"""
                match
                  $n0 isa user, has user-id "{node_id}";
                  {pattern}
                reduce $count = count;
                """
            )

        return run

    def _aggregation(self, _params: dict[str, Any]):
        answer = self._read(
            """
            match
              $u isa user, has user-id $id;
              (voter: $u, votee: $v) isa voted;
            reduce $votes = count groupby $id;
            sort $votes desc;
            limit 100;
            """
        )
        return list(answer.as_concept_rows())

    def _write_tick(self, params: dict[str, Any]):
        node_id = _id(params["id"])
        mark = int(params["mark"])
        self._write(
            [
                f"""
                match $u isa user, has user-id "{node_id}";
                update $u has benchmark-mark {mark};
                """
            ]
        )
