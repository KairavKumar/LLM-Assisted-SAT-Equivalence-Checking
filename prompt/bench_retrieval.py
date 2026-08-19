#!/usr/bin/env python3
"""
Targeted retrieval helper for large AIG-style BENCH files.

This local copy exists so the root-level llm_step1_prepare.py and
llm_step2_prepare.py can run against the user's current workspace layout.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


_TOKEN_RE = re.compile(r"[A-Za-z]+|\d+")
_NAT_RE = re.compile(r"(\d+)")
_BORING_NAME_RE = re.compile(r"^(?:n|t)\d+$")
_BORING_STEM_RE = re.compile(r"^(?:n|t)\d*$")
_CONST_NAME_RE = re.compile(r"^__(?:const|inv)")


def natural_key(text: str):
    return [int(part) if part.isdigit() else part.lower() for part in _NAT_RE.split(text)]


def tokenize(text: str) -> List[str]:
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


def stem_name(name: str) -> str:
    return re.sub(r"(_\d+)+$", "", name)


def is_boring_name(name: str) -> bool:
    clean = name.strip()
    stem = stem_name(clean)
    return bool(
        _BORING_NAME_RE.match(clean)
        or _BORING_STEM_RE.match(stem)
        or _CONST_NAME_RE.match(clean)
        or clean.startswith("$")
    )


def looks_like_interface_name(name: str) -> bool:
    if is_boring_name(name):
        return False
    tokens = tokenize(name)
    if not tokens:
        return False
    strong_tokens = {
        "sum", "acc", "prod", "product", "out", "output", "carry", "cout", "cin",
        "stage", "pipe", "mul", "add", "abc", "ab", "bc", "pp", "sq", "t2", "t4",
        "result", "y", "s", "partial",
    }
    return any(tok in strong_tokens for tok in tokens) or "_" in name


@dataclass
class SearchHit:
    name: str
    kind: str
    score: float
    source: str
    extra: str = ""


class BenchIndex:
    def __init__(self, bench_path: str):
        self.path = Path(bench_path)
        self.inputs: set[str] = set()
        self.outputs: set[str] = set()
        self.defs: Dict[str, Tuple[str, ...]] = {}
        self.line_no: Dict[str, int] = {}
        self.raw_lines: Dict[str, str] = {}
        self.fanouts: Dict[str, set[str]] = defaultdict(set)
        self.family_index: Dict[str, List[str]] = defaultdict(list)
        self._parse()

    def _parse(self):
        with self.path.open() as f:
            for lineno, raw in enumerate(f, 1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue

                m = re.match(r"INPUT\(([^)]+)\)", line)
                if m:
                    name = m.group(1)
                    self.inputs.add(name)
                    self.line_no[name] = lineno
                    self.raw_lines[name] = line
                    self.family_index[stem_name(name)].append(name)
                    continue

                m = re.match(r"OUTPUT\(([^)]+)\)", line)
                if m:
                    name = m.group(1)
                    self.outputs.add(name)
                    self.line_no[name] = lineno
                    self.raw_lines[name] = line
                    self.family_index[stem_name(name)].append(name)
                    continue

                m = re.match(r"(\w+)\s*=\s*NOT\((\w+)\)", line)
                if m:
                    out, a = m.groups()
                    self.defs[out] = ("NOT", a)
                else:
                    m = re.match(r"(\w+)\s*=\s*AND\((\w+),\s*(\w+)\)", line)
                    if m:
                        out, a, b = m.groups()
                        self.defs[out] = ("AND", a, b)
                    else:
                        m = re.match(r"(\w+)\s*=\s*(\w+)\s*$", line)
                        if not m:
                            raise ValueError(f"Unparsed BENCH line {lineno}: {line}")
                        out, a = m.groups()
                        self.defs[out] = ("BUF", a)

                out = line.split("=")[0].strip()
                self.line_no[out] = lineno
                self.raw_lines[out] = line
                self.family_index[stem_name(out)].append(out)

        for out, gate in self.defs.items():
            for fin in gate[1:]:
                self.fanouts[fin].add(out)

        for stem, names in self.family_index.items():
            names.sort(key=natural_key)

    @property
    def nodes(self) -> List[str]:
        merged = set(self.inputs) | set(self.outputs) | set(self.defs.keys())
        return sorted(merged, key=natural_key)

    def exists(self, name: str) -> bool:
        return name in self.inputs or name in self.outputs or name in self.defs

    def gate_type(self, name: str) -> str:
        if name in self.inputs:
            return "INPUT"
        if name in self.defs:
            return self.defs[name][0]
        if name in self.outputs:
            return "OUTPUT_ALIAS"
        return "UNKNOWN"

    def family(self, name_or_prefix: str) -> List[str]:
        if name_or_prefix in self.family_index:
            return self.family_index[name_or_prefix]
        stem = stem_name(name_or_prefix)
        if stem in self.family_index:
            return self.family_index[stem]
        prefix_matches = [n for n in self.nodes if n.startswith(name_or_prefix)]
        return sorted(prefix_matches, key=natural_key)

    def fanins(self, name: str) -> List[str]:
        if name not in self.defs:
            return []
        return list(self.defs[name][1:])

    def local_cone(
        self,
        root: str,
        fanin_depth: int = 2,
        fanout_depth: int = 1,
        max_fanout_nodes: int = 20,
        max_defining_lines: int = 40,
    ) -> Dict[str, List[str]]:
        if not self.exists(root):
            raise ValueError(f"Node not found in BENCH: {root}")

        fanin_seen = {root}
        fanin_order: List[str] = []
        q = deque([(root, 0)])
        while q:
            node, depth = q.popleft()
            if node != root:
                fanin_order.append(node)
            if depth >= fanin_depth:
                continue
            for fin in self.fanins(node):
                if fin not in fanin_seen:
                    fanin_seen.add(fin)
                    q.append((fin, depth + 1))

        fanout_seen = {root}
        fanout_order: List[str] = []
        q = deque([(root, 0)])
        while q:
            node, depth = q.popleft()
            if node != root:
                if len(fanout_order) >= max_fanout_nodes:
                    continue
                fanout_order.append(node)
            if depth >= fanout_depth:
                continue
            for fout in sorted(self.fanouts.get(node, []), key=natural_key):
                if fout not in fanout_seen:
                    fanout_seen.add(fout)
                    q.append((fout, depth + 1))

        subnodes = set([root]) | set(fanin_order) | set(fanout_order)
        defining_lines = [
            self.raw_lines[n]
            for n in sorted(subnodes, key=lambda n: self.line_no.get(n, 10**9))
            if n in self.raw_lines
        ][:max_defining_lines]

        return {
            "fanin_nodes": sorted(fanin_order, key=natural_key),
            "fanout_nodes": sorted(fanout_order, key=natural_key),
            "defining_lines": defining_lines,
        }


class JsonIndex:
    def __init__(self, json_path: str):
        self.path = Path(json_path)
        self.top_module = ""
        self.net_to_bits: Dict[str, List[int | str]] = {}
        self.bit_to_nets: Dict[int | str, List[str]] = defaultdict(list)
        self.cells: List[Tuple[str, str, Dict[str, List[int | str]]]] = []
        self._parse()

    def _parse(self):
        data = json.loads(self.path.read_text())
        modules = data.get("modules", {})
        if not modules:
            return
        top_name = None
        for mod_name, mod in modules.items():
            attrs = mod.get("attributes", {})
            if attrs.get("top") == "00000000000000000000000000000001":
                top_name = mod_name
                break
        if top_name is None:
            top_name = next(iter(modules))
        self.top_module = top_name
        mod = modules[top_name]

        for net_name, net in mod.get("netnames", {}).items():
            bits = list(net.get("bits", []))
            self.net_to_bits[net_name] = bits
            for bit in bits:
                self.bit_to_nets[bit].append(net_name)

        for cell_name, cell in mod.get("cells", {}).items():
            self.cells.append((cell_name, cell.get("type", ""), cell.get("connections", {})))

    def search_netnames(self, query: str, limit: int = 12) -> List[str]:
        q = query.lower()
        hits = []
        for name in self.net_to_bits:
            n = name.lower()
            if n == q or n.startswith(q) or q in n:
                hits.append(name)
        hits.sort(key=natural_key)
        return hits[:limit]

    def local_window(
        self,
        seeds: Iterable[str],
        max_netnames: int = 12,
        max_cells: int = 24,
    ) -> Dict[str, List[str]]:
        seed_list = list(seeds)
        chosen_netnames: List[str] = []
        seen_nets = set()
        seed_bits = set()

        for seed in seed_list:
            for net in self.search_netnames(seed, limit=max_netnames):
                if net not in seen_nets:
                    seen_nets.add(net)
                    chosen_netnames.append(net)
                for bit in self.net_to_bits.get(net, []):
                    seed_bits.add(bit)
            if seed in self.net_to_bits and seed not in seen_nets:
                seen_nets.add(seed)
                chosen_netnames.append(seed)
                for bit in self.net_to_bits.get(seed, []):
                    seed_bits.add(bit)

        chosen_cells = []
        for cell_name, cell_type, conns in self.cells:
            cell_bits = set()
            for bits in conns.values():
                cell_bits.update(bits)
            if seed_bits & cell_bits:
                conn_parts = []
                for port, bits in sorted(conns.items()):
                    conn_parts.append(f"{port}={bits[:6]}")
                chosen_cells.append(f"{cell_name} | {cell_type} | " + ", ".join(conn_parts))
            if len(chosen_cells) >= max_cells:
                break

        return {
            "netnames": chosen_netnames[:max_netnames],
            "cells": chosen_cells[:max_cells],
        }


class MappingIndex:
    def __init__(self, mapping_path: str):
        self.path = Path(mapping_path)
        self.verilog_to_bench: Dict[str, set[str]] = defaultdict(set)
        self.bench_to_verilog: Dict[str, List[str]] = defaultdict(list)
        self._parse()

    def _parse(self):
        data = json.loads(self.path.read_text())

        if "inputs" in data or "intermediates" in data or "outputs" in data:
            sections = []
            for key in ("inputs", "intermediates", "outputs"):
                if key in data:
                    sections.append(data[key])
            for section in sections:
                for bench_name, entry in section.items():
                    verilog_names = entry.get("verilog_names", [])
                    for vname in verilog_names:
                        self.verilog_to_bench[vname].add(bench_name)
                        self.bench_to_verilog[bench_name].append(vname)
            return

        rtl_to_bench = data.get("rtl_to_bench", {})
        for vname, bench_names in rtl_to_bench.items():
            for bench_name in bench_names:
                self.verilog_to_bench[vname].add(bench_name)
                self.bench_to_verilog[bench_name].append(vname)

    def search(self, query: str, limit: int = 10) -> List[SearchHit]:
        hits: Dict[Tuple[str, str], SearchHit] = {}
        q = query.lower()
        q_tokens = set(tokenize(query))

        for vname, bench_names in self.verilog_to_bench.items():
            source = f"{vname} -> {','.join(sorted(bench_names, key=natural_key)[:3])}"
            score = 0.0
            kind = ""

            if vname.lower() == q:
                score, kind = 1.0, "mapping_exact"
            elif q in vname.lower():
                score, kind = 0.94, "mapping_substring"
            else:
                v_tokens = set(tokenize(vname))
                overlap = len(q_tokens & v_tokens)
                if overlap:
                    score = 0.75 + 0.03 * overlap
                    kind = "mapping_token"
                else:
                    ratio = difflib.SequenceMatcher(None, q, vname.lower()).ratio()
                    if ratio >= 0.65:
                        score, kind = ratio, "mapping_fuzzy"

            if kind:
                for bench_name in bench_names:
                    key = (bench_name, kind)
                    prev = hits.get(key)
                    hit = SearchHit(bench_name, kind, score, "mapping", source)
                    if prev is None or hit.score > prev.score:
                        hits[key] = hit

        out = list(hits.values())
        out.sort(key=lambda h: (-h.score, natural_key(h.name)))
        return out[:limit]

    def aliases_for_bench(self, bench_name: str, limit: int = 12) -> List[str]:
        vals = sorted(set(self.bench_to_verilog.get(bench_name, [])), key=natural_key)
        return vals[:limit]


def search_bench_names(index: BenchIndex, query: str, limit: int = 15) -> List[SearchHit]:
    q = query.lower()
    q_tokens = set(tokenize(query))
    hits: Dict[str, SearchHit] = {}

    for name in index.nodes:
        n = name.lower()
        score = 0.0
        kind = ""

        if n == q:
            score, kind = 1.0, "exact"
        elif n.startswith(q):
            score, kind = 0.97, "prefix"
        elif q in n:
            score, kind = 0.93, "substring"
        else:
            n_tokens = set(tokenize(name))
            overlap = len(q_tokens & n_tokens)
            if overlap:
                score = 0.74 + 0.03 * overlap
                kind = "token"
            else:
                ratio = difflib.SequenceMatcher(None, q, n).ratio()
                if ratio >= 0.68:
                    score, kind = ratio, "fuzzy"

        if kind:
            hits[name] = SearchHit(name, kind, score, "bench", index.gate_type(name))

    out = list(hits.values())
    out.sort(key=lambda h: (-h.score, natural_key(h.name)))
    return out[:limit]


def format_hits(hits: Iterable[SearchHit], bench: BenchIndex | None = None) -> str:
    lines = []
    for hit in hits:
        line = f"{hit.name} | {hit.kind} | score={hit.score:.2f} | source={hit.source}"
        if hit.extra:
            line += f" | {hit.extra}"
        if bench is not None and hit.name in bench.line_no:
            line += f" | line={bench.line_no[hit.name]}"
        lines.append(line)
    return "\n".join(lines) if lines else "[no matches]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Targeted retrieval helper for large BENCH files")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search")
    p.add_argument("--bench", required=True)
    p.add_argument("--mapping")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=15)

    p = sub.add_parser("family")
    p.add_argument("--bench", required=True)
    p.add_argument("target")
    p.add_argument("--limit", type=int, default=40)

    p = sub.add_parser("locality")
    p.add_argument("--bench", required=True)
    p.add_argument("target")
    p.add_argument("--fanin-depth", type=int, default=2)
    p.add_argument("--fanout-depth", type=int, default=1)
    p.add_argument("--family-limit", type=int, default=12)
    p.add_argument("--max-fanout-nodes", type=int, default=20)
    p.add_argument("--max-defining-lines", type=int, default=40)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "search":
        bench = BenchIndex(args.bench)
        print("[bench_matches]")
        print(format_hits(search_bench_names(bench, args.query, limit=args.limit), bench=bench))
        if args.mapping:
            print("\n[mapping_matches]")
            print(format_hits(MappingIndex(args.mapping).search(args.query, limit=args.limit), bench=bench))
        return

    if args.cmd == "family":
        bench = BenchIndex(args.bench)
        family = bench.family(args.target)[: args.limit]
        if not family:
            print("[no family matches]")
            return
        print(f"family_size={len(family)}")
        for name in family:
            print(f"{name} | {bench.gate_type(name)} | line={bench.line_no.get(name, '-')}")
        return

    if args.cmd == "locality":
        bench = BenchIndex(args.bench)
        cone = bench.local_cone(
            args.target,
            fanin_depth=args.fanin_depth,
            fanout_depth=args.fanout_depth,
            max_fanout_nodes=args.max_fanout_nodes,
            max_defining_lines=args.max_defining_lines,
        )
        print(f"node={args.target}")
        if args.target in bench.raw_lines:
            print(f"definition={bench.raw_lines[args.target]}")
        print("[fanin_nodes]")
        for name in cone["fanin_nodes"]:
            print(name)
        print("[fanout_nodes]")
        for name in cone["fanout_nodes"]:
            print(name)
        print("[defining_lines]")
        for line in cone["defining_lines"]:
            print(line)


if __name__ == "__main__":
    main()
