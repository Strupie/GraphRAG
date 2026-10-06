"""Build the Microsoft GraphRAG index for the farm notes."""

from __future__ import annotations

import asyncio
import sys

from graphrag.api import build_index
from graphrag.index.validate_config import validate_config_names

from app.runtime import prepare


def main() -> None:
    config = prepare()
    validate_config_names(config)
    results = asyncio.run(build_index(config=config, verbose=True))
    failed = False
    for result in results:
        if result.error is not None:
            failed = True
            print(f"{result.workflow}: {result.error}", file=sys.stderr)
        else:
            print(f"{result.workflow}: success")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
