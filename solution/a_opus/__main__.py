"""python -m solution.a_opus --out <csv>  -- see pipeline.py and README.md."""

import os
import sys

try:
    import numpy  # noqa: F401  (checked here so a missing install reads as one message, not a trace)
except ImportError:
    venv_python = os.path.join(".venv", "Scripts", "python.exe") if os.name == "nt" \
        else os.path.join(".venv", "bin", "python")
    sys.exit("numpy is not installed for this Python ({0}).\n"
             "Create an environment with the pinned versions and run with its interpreter:\n"
             "    \"{0}\" -m venv .venv\n"
             "    {1} -m pip install -r solution/a_opus/requirements.txt\n"
             "    {1} -m solution.a_opus --out <csv>\n"
             "The run instructions are in solution/a_opus/README.md.".format(sys.executable,
                                                                             venv_python))

from .pipeline import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
