import os

from dotenv import load_dotenv

from benchmark.adapters.bolt import BoltAdapter

load_dotenv()


class Neo4jAuraAdapter(BoltAdapter):
    def __init__(self) -> None:
        super().__init__(
            name="Neo4j Aura",
            uri=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD"),
        )
