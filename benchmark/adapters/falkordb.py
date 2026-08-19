import os

from dotenv import load_dotenv
from falkordb import FalkorDB

from benchmark.adapters.base import DatabaseAdapter

load_dotenv()


def _inject_password(uri: str | None, password: str | None) -> str | None:
    if not uri or not password:
        return uri

    scheme, rest = uri.split("://", 1)

    if "@" in rest:
        userinfo, host = rest.rsplit("@", 1)
        if ":" not in userinfo:
            userinfo = f"{userinfo}:{password}"
        rest = f"{userinfo}@{host}"
    else:
        rest = f":{password}@{rest}"

    return f"{scheme}://{rest}"


class FalkorDBCloudAdapter(DatabaseAdapter):
    def __init__(self) -> None:
        self.name = "FalkorDB Cloud"
        self.uri = _inject_password(
            os.getenv("FALKORDB_URI"),
            os.getenv("FALKORDB_PASSWORD"),
        )
        self.graph_name = os.getenv("FALKORDB_DATABASE", "falkordb")
        self.db = None
        self.graph = None

        if not os.getenv("FALKORDB_URI"):
            raise ValueError("FalkorDB Cloud URI is not set.")

    def connect(self) -> None:
        self.db = FalkorDB.from_url(self.uri)
        self.graph = self.db.select_graph(self.graph_name)
        self.graph.query("RETURN 1")

    def execute(
        self,
        query: str,
        params: dict | None = None,
    ) -> None:
        if self.graph is None:
            raise RuntimeError(f"{self.name} connection is not open.")

        self.graph.query(query, params or {})

    def execute_value(
        self,
        query: str,
        params: dict | None = None,
    ):
        if self.graph is None:
            raise RuntimeError(f"{self.name} connection is not open.")

        result = self.graph.query(query, params or {})
        rows = getattr(result, "result_set", None) or []

        if not rows:
            return None

        return rows[0][0]

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
            self.db = None
            self.graph = None