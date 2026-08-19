import os

from dotenv import load_dotenv

from benchmark.adapters.bolt import BoltAdapter

load_dotenv()


class MemgraphCloudAdapter(BoltAdapter):
    def __init__(self) -> None:
        uri = os.getenv("MEMGRAPH_URI")

        if uri and uri.startswith("bolt+s://") and not uri.startswith("bolt+ssc://"):
            uri = "bolt+ssc://" + uri.removeprefix("bolt+s://")

        super().__init__(
            name="Memgraph Cloud",
            uri=uri,
            username=os.getenv("MEMGRAPH_USERNAME"),
            password=os.getenv("MEMGRAPH_PASSWORD"),
            database=os.getenv("MEMGRAPH_DATABASE", "memgraph"),
        )
