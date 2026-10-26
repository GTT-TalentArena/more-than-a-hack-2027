"""python -m heldout {fetch,convert,run,report} ... (issue #47; see heldout/README.md)."""

import sys

COMMANDS = ("fetch", "convert", "run", "report")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__.strip())
        return 0 if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help") else 2
    command = sys.argv.pop(1)
    module = __import__("heldout." + command, fromlist=["main"])
    return module.main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
