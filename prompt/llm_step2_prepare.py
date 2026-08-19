#!/usr/bin/env python3
"""
llm_step2_prepare.py

Prepare the second-step evidence packet for the LLM after STEP 1 has returned
targeted retrieval requests.

This script consumes a request JSON from the LLM and expands it into a compact
evidence bundle using BENCH locality/family/search lookups and optional mapping
lookups. The resulting text is meant to be pasted into the second LLM prompt.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench_retrieval import (
    BenchIndex,
    JsonIndex,
    MappingIndex,
    format_hits,
    natural_key,
    search_bench_names,
)


def load_request_json(path: str) -> dict:
    text = Path(path).read_text()
    normalized = (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    return json.loads(normalized)


def circuit_bundle(label: str, bench_path: str, mapping_path: str | None, json_path: str | None):
    return {
        "label": label,
        "bench": BenchIndex(bench_path),
        "mapping": MappingIndex(mapping_path) if mapping_path else None,
        "json": JsonIndex(json_path) if json_path else None,
        "bench_path": bench_path,
        "mapping_path": mapping_path,
        "json_path": json_path,
    }


def mapping_lookup(mapping: MappingIndex | None, query: str, limit: int) -> str:
    if mapping is None:
        return "[no mapping provided]"
    hits = mapping.search(query, limit=limit)
    return format_hits(hits)


def family_dump(bench: BenchIndex, target: str, limit: int) -> str:
    family = bench.family(target)[:limit]
    if not family:
        return "[no family matches]"
    lines = [f"family_size={len(family)}"]
    for name in family:
        lines.append(f"{name} | {bench.gate_type(name)} | line={bench.line_no.get(name, '-')}")
    return "\n".join(lines)


def json_window_dump(json_index: JsonIndex | None, seeds: list[str], net_limit: int, cell_limit: int) -> str:
    if json_index is None:
        return "[no yosys json provided]"
    window = json_index.local_window(seeds, max_netnames=net_limit, max_cells=cell_limit)
    lines = [f"top_module={json_index.top_module or '[unknown]'}"]
    if window["netnames"]:
        lines.append("[json_netnames]")
        lines.extend(window["netnames"])
    if window["cells"]:
        lines.append("[json_cells]")
        lines.extend(window["cells"])
    if len(lines) == 1:
        lines.append("[no local json matches]")
    return "\n".join(lines)


def locality_dump(
    bench: BenchIndex,
    mapping: MappingIndex | None,
    json_index: JsonIndex | None,
    target: str,
    fanin_depth: int,
    fanout_depth: int,
    family_limit: int,
    max_fanout_nodes: int,
    max_defining_lines: int,
    json_net_limit: int,
    json_cell_limit: int,
) -> str:
    if not bench.exists(target):
        return f"[node not found: {target}]"
    lines = [
        f"node={target}",
        f"gate_type={bench.gate_type(target)}",
        f"line={bench.line_no.get(target, '-')}",
    ]
    if target in bench.raw_lines:
        lines.append(f"definition={bench.raw_lines[target]}")

    aliases = mapping.aliases_for_bench(target, limit=12) if mapping is not None else []
    if aliases:
        lines.append("\n[mapping_aliases]")
        lines.extend(aliases)

    family = bench.family(target)[:family_limit]
    if family:
        lines.append("\n[family]")
        for name in family:
            lines.append(f"{name} | {bench.gate_type(name)} | line={bench.line_no.get(name, '-')}")

    cone = bench.local_cone(
        target,
        fanin_depth=fanin_depth,
        fanout_depth=fanout_depth,
        max_fanout_nodes=max_fanout_nodes,
        max_defining_lines=max_defining_lines,
    )
    if cone["fanin_nodes"]:
        lines.append("\n[fanin_nodes]")
        for name in cone["fanin_nodes"]:
            lines.append(f"{name} | {bench.gate_type(name)} | line={bench.line_no.get(name, '-')}")
    if cone["fanout_nodes"]:
        lines.append("\n[fanout_nodes]")
        for name in cone["fanout_nodes"]:
            lines.append(f"{name} | {bench.gate_type(name)} | line={bench.line_no.get(name, '-')}")
    if cone["defining_lines"]:
        lines.append("\n[defining_lines]")
        lines.extend(cone["defining_lines"])

    json_seeds = [target]
    json_seeds.extend(aliases)
    family_seed_count = 0
    for name in family:
        if family_seed_count >= 3:
            break
        json_seeds.append(name)
        family_seed_count += 1
    lines.append("\n[json_local_window]")
    lines.append(json_window_dump(json_index, json_seeds, net_limit=json_net_limit, cell_limit=json_cell_limit))
    return "\n".join(lines)


def resolve_bundle(circuits: dict, key: str):
    if key not in circuits:
        raise ValueError(f"Unknown circuit '{key}', expected one of {sorted(circuits)}")
    return circuits[key]


def render_evidence(args) -> str:
    request_data = load_request_json(args.request_json)
    circuits = {
        "A": circuit_bundle("A", args.bench_a, args.mapping_a, args.json_a),
        "B": circuit_bundle("B", args.bench_b, args.mapping_b, args.json_b),
    }

    semantic_targets = request_data.get("semantic_targets", [])
    requests = request_data.get("retrieval_requests", [])

    lines = [
        "You are doing STEP 2 of a two-step BENCH retrieval workflow for equivalence discovery.",
        "",
        "Your job in STEP 2:",
        "- use the semantic targets and retrieval evidence below",
        "- identify plausible equivalent BENCH node pairs across circuit A and circuit B",
        "- prefer recall over precision: DeepGate and SAT will filter later",
        "- include plausible candidates even if some may be false positives",
        "- still avoid obvious hallucinations or non-existent node names",
        "- prefer real BENCH node names that appear explicitly in the evidence below",
        "- actively look for cross-named but functionally matching nodes, not just identical BENCH names",
        "- if two nodes are the same arithmetic stage but appear under different names, include them",
        "",
        "Return exactly one valid JSON object and nothing else.",
        "Strict JSON rules:",
        "- use plain ASCII double quotes only",
        "- no smart quotes",
        "- no markdown fences",
        "- no comments",
        "- no trailing commas",
        "- every pair must appear inside pair_list",
        "- pair_list order must exactly match sub1_csv/sub2_csv order",
        "- sub1_csv and sub2_csv must have the same number of entries",
        "- do not include duplicate pairs",
        "",
        "Return exactly one JSON object in this shape:",
        "{",
        '  "pair_list": [',
        '    {"A": "<bench_node_in_A>", "B": "<bench_node_in_B>", "why": "<brief rationale>", "confidence": "high|medium|low"}',
        "  ],",
        '  "master_cli_ready": {',
        '    "sub1_csv": "<comma-separated A nodes>",',
        '    "sub2_csv": "<comma-separated B nodes>"',
        "  }",
        "}",
        "",
        "Important quality rules:",
        "- If you include a node in sub1_csv/sub2_csv, the same pair must also appear in pair_list.",
        "- Do not leave extra candidate pairs outside the JSON object.",
        "- Prefer same-name and clearly supported pairs first, but do not be overly conservative.",
        "- If a candidate is plausible from naming, mapping, or local structure, include it with lower confidence instead of omitting it.",
        "- Do not restrict yourself to same-name pairs.",
        "- Cross-named pairs are desirable when the evidence shows the same function/stage under different names.",
        "- Prefer semantic alignment in this order: same function and same bit index > same local cone role > same-name only.",
        "- Good examples of cross-named matches: an explicit intermediate bus in one circuit versus the hidden input operand bus of a later adder in the other circuit.",
        "",
        "[semantic_targets]",
        json.dumps(semantic_targets, indent=2),
        "",
        "[retrieval_evidence]",
    ]

    for idx, req in enumerate(requests, 1):
        rtype = req.get("type")
        circuit_key = req.get("circuit")
        bundle = resolve_bundle(circuits, circuit_key)
        bench = bundle["bench"]
        mapping = bundle["mapping"]
        json_index = bundle["json"]

        lines.append(f"\n--- request_{idx} ---")
        lines.append(json.dumps(req, indent=2, sort_keys=True))

        if rtype == "search":
            query = req["query"]
            limit = int(req.get("limit", args.default_limit))
            lines.append("[bench_matches]")
            lines.append(format_hits(search_bench_names(bench, query, limit=limit), bench=bench))
            lines.append("\n[mapping_matches]")
            lines.append(mapping_lookup(mapping, query, limit))
        elif rtype == "family":
            target = req["target"]
            limit = int(req.get("limit", args.family_limit))
            lines.append(family_dump(bench, target, limit))
            if mapping is not None:
                alias_hits = []
                family = bench.family(target)[: min(limit, 6)]
                for name in family:
                    aliases = mapping.aliases_for_bench(name, limit=4)
                    if aliases:
                        alias_hits.append(f"{name} -> {', '.join(aliases)}")
                if alias_hits:
                    lines.append("\n[family_mapping_aliases]")
                    lines.extend(alias_hits)
        elif rtype == "locality":
            target = req["target"]
            lines.append(
                locality_dump(
                    bench,
                    mapping,
                    json_index,
                    target,
                    fanin_depth=int(req.get("fanin_depth", args.fanin_depth)),
                    fanout_depth=int(req.get("fanout_depth", args.fanout_depth)),
                    family_limit=args.family_limit,
                    max_fanout_nodes=args.max_fanout_nodes,
                    max_defining_lines=args.max_defining_lines,
                    json_net_limit=args.json_net_limit,
                    json_cell_limit=args.json_cell_limit,
                )
            )
        elif rtype == "mapping_lookup":
            query = req["query"]
            limit = int(req.get("limit", args.default_limit))
            lines.append(mapping_lookup(mapping, query, limit))
        else:
            lines.append(f"[unsupported request type: {rtype}]")

    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare the second-step LLM evidence packet")
    parser.add_argument("--bench-a", required=True, help="Circuit A BENCH file")
    parser.add_argument("--bench-b", required=True, help="Circuit B BENCH file")
    parser.add_argument("--mapping-a", help="Optional Circuit A mapping JSON")
    parser.add_argument("--mapping-b", help="Optional Circuit B mapping JSON")
    parser.add_argument("--json-a", help="Optional Circuit A Yosys JSON")
    parser.add_argument("--json-b", help="Optional Circuit B Yosys JSON")
    parser.add_argument("--request-json", required=True, help="JSON file containing semantic_targets and retrieval_requests")
    parser.add_argument("--default-limit", type=int, default=12, help="Default result limit for search/mapping lookups")
    parser.add_argument("--family-limit", type=int, default=12, help="Default family display limit")
    parser.add_argument("--fanin-depth", type=int, default=2, help="Default locality fanin depth")
    parser.add_argument("--fanout-depth", type=int, default=1, help="Default locality fanout depth")
    parser.add_argument("--max-fanout-nodes", type=int, default=20, help="Locality fanout node cap")
    parser.add_argument("--max-defining-lines", type=int, default=40, help="Locality defining-line cap")
    parser.add_argument("--json-net-limit", type=int, default=12, help="JSON-locality netname cap")
    parser.add_argument("--json-cell-limit", type=int, default=24, help="JSON-locality cell cap")
    parser.add_argument("--output", help="Optional output file for the generated evidence packet")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    packet = render_evidence(args)
    if args.output:
        Path(args.output).write_text(packet)
    else:
        print(packet, end="")


if __name__ == "__main__":
    main()
