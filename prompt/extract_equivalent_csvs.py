#!/usr/bin/env python3
"""
Extract aligned equivalent-node CSVs from an LLM JSON response.

Input JSON shape:
{
  "pair_list": [
    {"A": "node_in_circuit_A", "B": "node_in_circuit_B", ...},
    ...
  ],
  "master_cli_ready": {
    "sub1_csv": "...",
    "sub2_csv": "..."
  }
}

The script prefers `pair_list` so order is explicit and easy to validate.
If `pair_list` is missing, it falls back to `master_cli_ready.sub1_csv/sub2_csv`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: str) -> dict:
    text = Path(path).read_text()
    normalized = (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    return json.loads(normalized)


def split_csv(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def extract_lists(data: dict) -> tuple[list[str], list[str]]:
    pair_list = data.get("pair_list")
    if isinstance(pair_list, list) and pair_list:
        left: list[str] = []
        right: list[str] = []
        for idx, pair in enumerate(pair_list, 1):
            if not isinstance(pair, dict):
                raise ValueError(f"pair_list[{idx}] is not an object")
            a = pair.get("A")
            b = pair.get("B")
            if not a or not b:
                raise ValueError(f"pair_list[{idx}] must contain non-empty A and B fields")
            left.append(a)
            right.append(b)
        return left, right

    cli = data.get("master_cli_ready", {})
    if isinstance(cli, dict):
        left = split_csv(cli.get("sub1_csv", ""))
        right = split_csv(cli.get("sub2_csv", ""))
        if left or right:
            return left, right

    raise ValueError("Could not find pair_list or master_cli_ready.sub1_csv/sub2_csv in input JSON")


def validate_lists(left: list[str], right: list[str], allow_duplicates: bool) -> None:
    if len(left) != len(right):
        raise ValueError(f"List length mismatch: {len(left)} nodes in A vs {len(right)} nodes in B")
    if not left:
        raise ValueError("No equivalent-node pairs found")

    if not allow_duplicates:
        dup_a = sorted({name for name in left if left.count(name) > 1})
        dup_b = sorted({name for name in right if right.count(name) > 1})
        if dup_a:
            raise ValueError(f"Duplicate nodes in A list: {', '.join(dup_a[:10])}")
        if dup_b:
            raise ValueError(f"Duplicate nodes in B list: {', '.join(dup_b[:10])}")


def write_csv(path: str, values: list[str]) -> None:
    Path(path).write_text(",".join(values) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract aligned equivalent-node CSVs from LLM JSON")
    parser.add_argument("--input", required=True, help="LLM JSON file containing pair_list or master_cli_ready")
    parser.add_argument("--csv-a", default="equiv_nodes_a.csv", help="Output CSV for circuit A node list")
    parser.add_argument("--csv-b", default="equiv_nodes_b.csv", help="Output CSV for circuit B node list")
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Allow duplicate node names inside either output list",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_json(args.input)
    left, right = extract_lists(data)
    validate_lists(left, right, allow_duplicates=args.allow_duplicates)
    write_csv(args.csv_a, left)
    write_csv(args.csv_b, right)
    print(f"Wrote {len(left)} aligned pairs")
    print(f"A CSV: {args.csv_a}")
    print(f"B CSV: {args.csv_b}")


if __name__ == "__main__":
    main()
