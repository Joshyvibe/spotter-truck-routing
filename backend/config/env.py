"""Load ``backend/.env`` for local runs (Docker and the host pass real env vars instead).
Existing environment variables always win."""

import os
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_dotenv(path: Path = DEFAULT_PATH) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.split(" #", 1)[0].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip("'\""))
