"""Benchmark invented full-length ATD only; output contains aggregate timings."""

import json
import platform
import random
import tempfile
import time

import games
from .synthetic import write_fixture
from .tracking import IndexedTracking


def main():
    with tempfile.TemporaryDirectory(prefix="gtt-viewer-synthetic-") as directory:
        count = games.source_frames()
        meta, raw = write_fixture(directory, count, slots=46)
        source = IndexedTracking(meta, raw)
        rng = random.Random(34)
        times = []
        for frame in [0, count-1, 90651, 110808] + [rng.randrange(count) for _ in range(96)]:
            started = time.perf_counter()
            source.window(frame, min(125, count-frame))
            times.append((time.perf_counter()-started)*1000)
        times.sort()
        print(json.dumps({"input": "fully synthetic ATD", "frames": count, "slots": 46,
                          "python": platform.python_version(), "platform": platform.system(),
                          "raw_bytes": raw.stat().st_size, "index_bytes": len(source.offsets)*source.offsets.itemsize,
                          "index_seconds": round(source.load_seconds,3), "windows": len(times),
                          "window_ms_p50": round(times[49],3), "window_ms_p95": round(times[94],3)}, indent=2))


if __name__ == '__main__':
    main()
