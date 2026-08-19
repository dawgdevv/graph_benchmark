from typing import Any

from neo4j import GraphDatabase

from benchmark.adapters.base import DatabaseAdapter


class BoltAdapter(DatabaseAdapter):
    def __init__(
        self,
        name: str,
        uri: str | None,
        username: str | None,
        password: str | None,
        database: str | None = None,
    ) -> None:
        self.name = name
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None

        if not self.uri:
            raise ValueError(f"{name} URI is not set.")

        if not self.username:
            raise ValueError(f"{name} username is not set.")

        if not self.password:
            raise ValueError(f"{name} password is not set.")

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
            raise RuntimeError(f"{self.name} connection is not open.")

        params = params or {}
        kwargs = {}

        if self.database:
            kwargs["database"] = self.database

        with self.driver.session(**kwargs) as session:
            session.run(query, params).consume()

    def execute_value(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ):
        if self.driver is None:
            raise RuntimeError(f"{self.name} connection is not open.")

        params = params or {}
        kwargs = {}

        if self.database:
            kwargs["database"] = self.database

        with self.driver.session(**kwargs) as session:
            result = session.run(query, params)
            record = result.single()

            if record is None:
                return None

            return record[0]

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()
            self.driver = None
