"""Convenience wrapper for the public availability check command."""

from portfolio_ops.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["check"]))
