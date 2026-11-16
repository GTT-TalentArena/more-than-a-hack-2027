"""python -m solution.a_dfl --out <csv>: candidate A with the DFL-trained ball-free model.

Every flag is candidate A's (solution/a_opus/pipeline.py). P0 runs modules with --out only (#26).
"""

import sys

from solution.a_opus import pipeline

from . import __version__
from .model import installed

if __name__ == "__main__":
    with installed() as model:
        print("[a_dfl] version {}: ball-free model trained on DFL {} ({} frames), fixed weight {:.2f}; "
              "nothing is fitted on this match".format(
                  __version__, "+".join(model["training"]["matches"]), model["training"]["frames"],
                  model["weight"]))
        sys.exit(pipeline.main(sys.argv[1:]))
