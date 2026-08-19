#!/usr/bin/env python3
"""
llm_step1_prepare.py

Prepare a stronger first-pass prompt packet for an LLM that will inspect two
Verilog designs and decide which BENCH/mapping evidence it wants next.

This version is intentionally more RTL-centric than the original:
- it includes the top-level Verilog source for both circuits
- it keeps the BENCH summary compact and biased toward RTL-relevant stems
- it asks the LLM for concrete retrieval requests rather than vague targets
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable, List

from bench_retrieval import (
    BenchIndex,
    MappingIndex,
    is_boring_name,
    looks_like_interface_name,
    natural_key,
    stem_name,
)


MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_]\w*)")
WIRE_RE = re.compile(r"\b(?:wire|reg|logic)\b\s*(?:\[[^]]+\]\s*)?([^;]+);")
IDENT_RE = re.compile(r"[A-Za-z_]\w*(?:\[\d+\])?")
INSTANTIATION_RE = re.compile(
    r"^\s*([A-Za-z_]\w*)\s+(?:#\s*\([^;]*?\)\s*)?([A-Za-z_]\w*)\s*\(",
    re.MULTILINE | re.DOTALL,
)


def read_text(path: str | None) -> str:
    return Path(path).read_text() if path else ""


def shorten(items: Iterable[str], limit: int) -> List[str]:
    out = list(items)
    return out[:limit]


def detect_top_module(text: str) -> str | None:
    modules = MODULE_RE.findall(text)
    if not modules:
        return None
    instantiated = {mod for mod, _ in INSTANTIATION_RE.findall(text) if mod != "module"}
    top_candidates = [mod for mod in modules if mod not in instantiated]
    if top_candidates:
        return top_candidates[0]
    return modules[0]


def extract_module_text(text: str, module_name: str | None) -> str:
    if not module_name:
        return text
    start_re = re.compile(rf"\bmodule\s+{re.escape(module_name)}\b")
    start = start_re.search(text)
    if not start:
        return text
    rest = text[start.start() :]
    end = re.search(r"\bendmodule\b", rest)
    if not end:
        return rest
    return rest[: end.end()]


def summarize_verilog(path: str, signal_limit: int, inst_limit: int) -> dict:
    text = read_text(path)
    modules = MODULE_RE.findall(text)

    wire_names: list[str] = []
    for block in WIRE_RE.findall(text):
        for name in IDENT_RE.findall(block):
            if name not in {"wire", "reg", "logic"}:
                wire_names.append(name)

    instances = []
    for mod, inst in INSTANTIATION_RE.findall(text):
        if mod != "module":
            instances.append(f"{mod}:{inst}")

    signal_stems = Counter(stem_name(name.replace("[", "_").replace("]", "")) for name in wire_names)
    instance_types = Counter(item.split(":")[0] for item in instances)

    return {
        "path": path,
        "modules": modules,
        "top_module": detect_top_module(text),
        "module_count": len(modules),
        "signal_examples": shorten(sorted(set(wire_names), key=natural_key), signal_limit),
        "signal_families": [name for name, _ in signal_stems.most_common(signal_limit)],
        "instance_types": [name for name, _ in instance_types.most_common(inst_limit)],
    }


def preferred_stems(verilog_summary: dict) -> list[str]:
    stems = []
    for key in ("signal_families", "signal_examples"):
        for name in verilog_summary.get(key, []):
            clean = stem_name(name.replace("[", "_").replace("]", ""))
            if clean and clean not in stems:
                stems.append(clean)
    return stems


def summarize_bench(path: str, family_limit: int, preferred: list[str], mapping: MappingIndex | None = None) -> dict:
    bench = BenchIndex(path)
    preferred_lc = [p.lower() for p in preferred if p]
    family_records = []

    for stem, names in bench.family_index.items():
        if len(names) < 2:
            continue
        if is_boring_name(stem):
            continue

        sample = names[: min(4, len(names))]
        mapping_aliases = 0
        if mapping is not None:
            seen_aliases = set()
            for bench_name in sample:
                seen_aliases.update(mapping.aliases_for_bench(bench_name, limit=8))
            mapping_aliases = len(seen_aliases)

        interesting_sample = any(looks_like_interface_name(name) for name in sample)
        if not interesting_sample and not looks_like_interface_name(stem) and mapping_aliases == 0:
            continue

        stem_lc = stem.lower()
        preferred_match = any(
            pref == stem_lc or pref in stem_lc or stem_lc in pref
            for pref in preferred_lc
        )
        output_hits = sum(1 for name in names if name in bench.outputs)
        defined_hits = sum(1 for name in names if name in bench.defs)
        fanout_score = sum(len(bench.fanouts.get(name, ())) for name in sample)

        family_records.append(
            {
                "stem": stem,
                "count": len(names),
                "sample": sample,
                "preferred_match": preferred_match,
                "mapping_aliases": mapping_aliases,
                "output_hits": output_hits,
                "defined_hits": defined_hits,
                "fanout_score": fanout_score,
            }
        )

    family_records.sort(
        key=lambda item: (
            not item["preferred_match"],
            -item["mapping_aliases"],
            -item["output_hits"],
            -item["fanout_score"],
            -item["count"],
            natural_key(item["stem"]),
        )
    )

    interesting = []
    for item in family_records[:family_limit]:
        kind = []
        if item["preferred_match"]:
            kind.append("rtl_aligned")
        if item["mapping_aliases"]:
            kind.append("mapping_backed")
        if item["output_hits"]:
            kind.append("interface_like")
        interesting.append(
            {
                "stem": item["stem"],
                "count": item["count"],
                "sample": item["sample"],
                "kind": kind or ["structural"],
                "mapping_alias_count": item["mapping_aliases"],
                "sample_fanout_score": item["fanout_score"],
            }
        )

    return {
        "path": path,
        "inputs": len(bench.inputs),
        "outputs": len(bench.outputs),
        "defined_nodes": len(bench.defs),
        "naming_policy": "anonymous temp stems like n1234/t456 are suppressed unless recovered via mapping/RTL names",
        "interesting_families": interesting,
    }


def summarize_mapping(path: str | None, limit: int, preferred: list[str]) -> dict | None:
    if not path:
        return None
    mapping = MappingIndex(path)
    preferred_lc = [p.lower() for p in preferred if p]
    entries = []
    for vname, bench_names in mapping.verilog_to_bench.items():
        if is_boring_name(vname):
            continue
        score = (
            any(pref == vname.lower() or pref in vname.lower() or vname.lower() in pref for pref in preferred_lc),
            looks_like_interface_name(vname),
            len(bench_names),
        )
        entries.append((score, vname, bench_names))
    entries.sort(key=lambda item: (-int(item[0][0]), -int(item[0][1]), -item[0][2], natural_key(item[1])))
    sample = []
    for _, vname, bench_names in entries[:limit]:
        sample.append(
            {
                "verilog": vname,
                "bench": sorted(bench_names, key=natural_key)[: min(4, len(bench_names))],
            }
        )
    return {
        "path": path,
        "verilog_name_count": len(mapping.verilog_to_bench),
        "sample": sample,
    }


def source_block(path: str, max_chars: int) -> dict:
    text = read_text(path)
    top_module = detect_top_module(text)
    top_text = extract_module_text(text, top_module)
    clipped = top_text[:max_chars]
    if len(top_text) > max_chars:
        clipped += "\n// ... truncated for prompt size ..."
    return {
        "path": path,
        "top_module": top_module,
        "source": clipped,
    }


def build_packet(args) -> str:
    verilog_a = summarize_verilog(args.verilog_a, args.signal_limit, args.instance_limit)
    verilog_b = summarize_verilog(args.verilog_b, args.signal_limit, args.instance_limit)
    mapping_a_idx = MappingIndex(args.mapping_a) if args.mapping_a else None
    mapping_b_idx = MappingIndex(args.mapping_b) if args.mapping_b else None
    preferred_a = preferred_stems(verilog_a)
    preferred_b = preferred_stems(verilog_b)
    bench_a = summarize_bench(args.bench_a, args.family_limit, preferred_a, mapping_a_idx)
    bench_b = summarize_bench(args.bench_b, args.family_limit, preferred_b, mapping_b_idx)
    mapping_a = summarize_mapping(args.mapping_a, args.mapping_limit, preferred_a)
    mapping_b = summarize_mapping(args.mapping_b, args.mapping_limit, preferred_b)
    source_a = source_block(args.verilog_a, args.verilog_chars)
    source_b = source_block(args.verilog_b, args.verilog_chars)

    payload = {
        "artifacts": {
            "circuit_A": {
                "verilog": verilog_a,
                "bench": bench_a,
                "mapping": mapping_a,
            },
            "circuit_B": {
                "verilog": verilog_b,
                "bench": bench_b,
                "mapping": mapping_b,
            },
        }
    }

    instructions = """
You are doing STEP 1 of a two-step BENCH retrieval workflow for equivalence discovery.

Your job in STEP 1:
- read the top-level RTL plus the compact BENCH/mapping summaries below
- infer likely semantic cut-points / internal stage outputs
- DO NOT output final equivalent BENCH node pairs yet
- instead, request only the BENCH/mapping evidence you need next

What to optimize for:
- high-value arithmetic stage boundaries
- interface/module-boundary style nets and bus families
- repeated accumulator or bus families
- bottom-up verification order
- concrete names that can be retrieved in STEP 2
- recall over precision: it is OK to ask for plausible candidates that may later be filtered by DeepGate/SAT
- cross-named precursor stages: if the same function appears under different BENCH names, ask for both sides explicitly

What to avoid:
- anonymous temp-style nodes or stems like n1234, t456, $..., __const...
- asking for the whole BENCH
- requesting huge unstructured dumps
- overly broad targets that are hard to retrieve
- vague names like "carry chain", "output stage", or "partial product generation"

Prefer concrete semantic targets like:
- "sum_ab"
- "sum_abc"
- "t2"
- "t4"
- "u_mul2_acc"
- "u_mul4_acc"

Important:
- do NOT restrict yourself to same-name BENCH families
- if Circuit A exposes an intermediate stage that Circuit B hides under another name, request both
- especially look for "precursor" buses feeding a known same-name stage
- example pattern: Circuit A may expose an explicit a+b bus, while Circuit B may embed the same function as the input operand of a later adder

The BENCH summary is already filtered toward "interesting" names:
- interface-like preserved nets
- mapping-backed names
- RTL-aligned families
- bus stems that look like stage boundaries

Use STEP 1 to decide *which exact named families or nodes deserve local expansion next*.
If a family looks too large, ask for a few targeted locality requests around its representative nodes instead of requesting the whole family.
This stage is meant to reduce the m*n candidate explosion before DeepGate, not to prove equivalence.
So be willing to request a somewhat broader but still structured candidate set if it improves recall.
When you suspect a cross-named match, ask for retrieval on both names/families, not just the same-name side.

Allowed retrieval request types for STEP 2:
- {"type": "search", "circuit": "A|B", "query": "<string>", "limit": <int optional>}
- {"type": "family", "circuit": "A|B", "target": "<bench node or family prefix>", "limit": <int optional>}
- {"type": "locality", "circuit": "A|B", "target": "<bench node>", "fanin_depth": <int optional>, "fanout_depth": <int optional>}
- {"type": "mapping_lookup", "circuit": "A|B", "query": "<verilog signal name or prefix>", "limit": <int optional>}

Return exactly one JSON object in this shape:
{
  "semantic_targets": [
    {
      "name": "<concrete rtl-level stage or signal family>",
      "why": "<why it is a good candidate stage>",
      "expected_width": <int or null>,
      "priority": 1
    }
  ],
  "retrieval_requests": [
    {
      "type": "search|family|locality|mapping_lookup",
      "circuit": "A|B",
      "...": "request-specific fields"
    }
  ]
}

The BENCH is a very large AIG netlist. Treat the RTL as the primary semantic source.
Use the BENCH/mapping summary only to decide what targeted retrievals to ask for next.
""".strip()

    return (
        f"{instructions}\n\n"
        f"[verilog_source_A]\n{source_a['source']}\n\n"
        f"[verilog_source_B]\n{source_b['source']}\n\n"
        f"[artifact_summary]\n{json.dumps(payload, indent=2)}\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare the first-step LLM packet")
    parser.add_argument("--verilog-a", required=True, help="Circuit A Verilog file")
    parser.add_argument("--verilog-b", required=True, help="Circuit B Verilog file")
    parser.add_argument("--bench-a", required=True, help="Circuit A BENCH file")
    parser.add_argument("--bench-b", required=True, help="Circuit B BENCH file")
    parser.add_argument("--mapping-a", help="Optional Circuit A mapping JSON")
    parser.add_argument("--mapping-b", help="Optional Circuit B mapping JSON")
    parser.add_argument("--signal-limit", type=int, default=24, help="Max example Verilog signals per circuit")
    parser.add_argument("--instance-limit", type=int, default=16, help="Max instance/module types per circuit")
    parser.add_argument("--family-limit", type=int, default=14, help="Max BENCH families per circuit")
    parser.add_argument("--mapping-limit", type=int, default=16, help="Max mapping examples per circuit")
    parser.add_argument("--verilog-chars", type=int, default=8000, help="Max top-level Verilog chars per circuit")
    parser.add_argument("--output", help="Optional output file for the generated prompt packet")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    packet = build_packet(args)
    if args.output:
        Path(args.output).write_text(packet)
    else:
        print(packet, end="")


if __name__ == "__main__":
    main()
