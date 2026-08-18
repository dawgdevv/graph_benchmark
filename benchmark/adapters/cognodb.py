import os
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

from benchmark.adapters.base import DatabaseAdapter

load_dotenv()


class CognoDBAdapter(DatabaseAdapter):
    def __init__(self) -> None:
        self.uri = os.getenv("COGNODB_URI")
        self.username = os.getenv("COGNODB_USERNAME", "cognodb")
        self.password = os.getenv("COGNODB_PASSWORD")
        self.driver = None

        if not self.uri:
            raise ValueError("COGNODB_URI is not set.")

        if not self.password:
            raise ValueError("COGNODB_PASSWORD is not set.")

    def connect(self) -> None:
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
        )

        self.driver.verify_connectivity()

    def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        if self.driver is None:
            raise RuntimeError("CognoDB connection is not open.")

        params = params or {}

        with self.driver.session() as session:
            session.run(query, params).consume()

    def execute_value(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ):
        if self.driver is None:
            raise RuntimeError("CognoDB connection is not open.")

        params = params or {}

        with self.driver.session() as session:
            result = session.run(query, params)
            record = result.single()

            if record is None:
                return None

            return record[0]

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()
            self.driver = None