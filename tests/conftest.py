import os
import tempfile
from pathlib import Path

# the range keeps its state in a throw-away database during tests
os.environ["CYBERARENA_RANGE_DB"] = str(Path(tempfile.mkdtemp()) / "t.db")
os.environ["NOISE_MIN"] = os.environ["NOISE_MAX"] = "99999"
