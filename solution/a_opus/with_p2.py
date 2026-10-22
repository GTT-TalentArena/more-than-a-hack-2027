"""P3 variant: candidate A with the P2 detector on. P0 runs modules as `-m <module> --out <csv>`
with no other flags (#26), so the switch lives here: python -m solution.a_opus.with_p2 --out X."""
import sys

from .pipeline import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] + ["--set", "p2.enabled=1"]))
