from pathlib import Path
import gzip
import shutil
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.config import DATASET_DIR, RAW_DATASET_PATH


DATASET_URL = "https://snap.stanford.edu/data/wiki-Vote.txt.gz"
COMPRESSED_PATH = DATASET_DIR / "wiki-Vote.txt.gz"


def download_dataset() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    if RAW_DATASET_PATH.exists():
        print(f"Dataset already exists: {RAW_DATASET_PATH}")
        return

    print("Downloading SNAP Wiki-Vote dataset...")

    urllib.request.urlretrieve(
        DATASET_URL,
        COMPRESSED_PATH,
    )

    print("Extracting dataset...")

    with gzip.open(COMPRESSED_PATH, "rb") as compressed_file:
        with RAW_DATASET_PATH.open("wb") as output_file:
            shutil.copyfileobj(
                compressed_file,
                output_file,
            )

    COMPRESSED_PATH.unlink()

    print(f"Dataset ready: {RAW_DATASET_PATH}")


if __name__ == "__main__":
    download_dataset()