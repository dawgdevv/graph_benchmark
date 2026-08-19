import os

from dotenv import load_dotenv

from benchmark.adapters.bolt import BoltAdapter

load_dotenv()


class CognoDBAdapter(BoltAdapter):
    def __init__(self) -> None:
        super().__init__(
            name="CognoDB",
            uri=os.getenv("COGNODB_URI"),
            username=os.getenv("COGNODB_USERNAME", "cognodb"),
            password=os.getenv("COGNODB_PASSWORD"),
        )
