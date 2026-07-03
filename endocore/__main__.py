"""Allow `python -m endocore ...` as an alias for the `end` CLI."""

from endocore.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
