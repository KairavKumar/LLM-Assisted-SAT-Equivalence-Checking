#!/usr/bin/env python3
"""Run final.py solver on an existing miter and solve the final CNF."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from final import solver
from bench_utils import _parse_bench


def _read_list(path: Path) -> list[str]:
    items = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        items.append(s)
    return items


def _map_to_miter(name: str, suffix: str, miter_names: set[str]) -> str:
    if name in miter_names:
        return name
    if name.endswith("_bench1") or name.endswith("_bench2"):
        return name
    candidate = f"{name}{suffix}"
    if candidate in miter_names:
        return candidate
    return candidate


def kissat_sat(clauses, n_vars):
    if shutil.which("kissat") is None:
        raise RuntimeError("kissat not found in PATH")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".cnf", delete=False) as f:
        f.write(f"p cnf {n_vars} {len(clauses)}\n")
        for cl in clauses:
            f.write(" ".join(map(str, cl)) + " 0\n")
        cnf_path = f.name

    res = subprocess.run(["kissat", cnf_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode == 20:
        return True
    if res.returncode == 10:
        return False
    raise RuntimeError(f"kissat failed with code {res.returncode}")


def main():
    parser = argparse.ArgumentParser(description="Run final.py on an existing miter")
    parser.add_argument("miter", help="Path to miter .bench file")
    parser.add_argument("list_a", help="Path to list A (one node per line)")
    parser.add_argument("list_b", help="Path to list B (one node per line)")
    parser.add_argument("--out-cnf", default="out.cnf", help="Output CNF path")
    args = parser.parse_args()

    miter_path = Path(args.miter)
    list_a = _read_list(Path(args.list_a))
    list_b = _read_list(Path(args.list_b))

    if len(list_a) != len(list_b):
        raise SystemExit(f"List length mismatch: {len(list_a)} vs {len(list_b)}")

    pi_list, po_list, gate_defs = _parse_bench(str(miter_path))
    miter_names = set(pi_list) | set(po_list) | set(gate_defs.keys())

    miter_pairs = []
    for a, b in zip(list_a, list_b):
        a_name = _map_to_miter(a, "_bench1", miter_names)
        b_name = _map_to_miter(b, "_bench2", miter_names)
        miter_pairs.append((a_name, b_name))

    opt = solver(str(miter_path), kissat_sat)
    opt.process_pairs(miter_pairs)
    opt.write_final_cnf(args.out_cnf)
    opt.print_stats()

    # Run SAT on the final CNF
    res = subprocess.run(["kissat", args.out_cnf])
    if res.returncode == 10:
        print("Final CNF: SAT")
    elif res.returncode == 20:
        print("Final CNF: UNSAT")
    else:
        raise RuntimeError(f"kissat failed with code {res.returncode}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
