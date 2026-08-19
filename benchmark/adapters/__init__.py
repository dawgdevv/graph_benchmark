from benchmark.adapters.cognodb import CognoDBAdapter
from benchmark.adapters.falkordb import FalkorDBCloudAdapter
from benchmark.adapters.memgraph import MemgraphCloudAdapter
from benchmark.adapters.neo4j import Neo4jAuraAdapter
from benchmark.adapters.typedb import TypeDBCloudAdapter


def get_adapter(database_name: str):
    if database_name == "cognodb":
        return CognoDBAdapter()

    if database_name == "neo4j":
        return Neo4jAuraAdapter()

    if database_name == "memgraph":
        return MemgraphCloudAdapter()

    if database_name == "falkordb":
        return FalkorDBCloudAdapter()

    if database_name == "typedb":
        return TypeDBCloudAdapter()

    raise ValueError(f"Unknown database: {database_name}")
