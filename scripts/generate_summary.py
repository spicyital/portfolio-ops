"""Convenience wrapper for rebuilding generated public status files."""

from portfolio_ops.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["summary"]))
