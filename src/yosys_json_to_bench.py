#!/usr/bin/env python3
"""
yosys_json_to_bench.py
Convert Yosys JSON output (after aigmap) to BENCH format,
preserving original Verilog signal names.

Outputs:
  - <name>.bench       : BENCH file with AND/NOT gates only
  - <name>.mapping.json: Sidecar mapping from bench node IDs to Verilog signal names

Usage:
    yosys -p "read_verilog <filename>.v; hierarchy -top <top_module_name>; proc; flatten; opt; aigmap; opt_clean; write_json <output_name>.json"
    python3 yosys_json_to_bench.py design.json [--module top_module]
"""

import json
import argparse
import sys
import os
from collections import defaultdict


def verilog_bit_index(i, num_bits, offset, upto):
    """Compute the correct Verilog index for bits[i] given Yosys metadata.

    For descending ranges like [3:0]: offset=0, upto=0
        bits[0] -> index 0, bits[1] -> index 1, ...
    For ascending ranges like [0:1]: offset=0, upto=1
        bits[0] -> index 1, bits[1] -> index 0  (reversed)

    General formula accounts for arbitrary offset too, e.g. [4:7] or [7:4].
    """
    if upto:
        return offset + (num_bits - 1 - i)
    else:
        return offset + i


def sanitize_bench_name(name):
    """Replace characters unsafe for bench format.
    a[3] -> a_3,  bus[0] -> bus_0  etc."""
    return name.replace("[", "_").replace("]", "").replace(".", "_").replace("&", "_").replace("/", "_")


def load_yosys_json(path):
    with open(path) as f:
        return json.load(f)


def pick_module(data, module_name=None):
    modules = data["modules"]
    if module_name:
        if module_name not in modules:
            print(f"Error: module '{module_name}' not found. Available: {list(modules.keys())}")
            sys.exit(1)
        return module_name, modules[module_name]
    # Pick the first (usually only) module
    name = list(modules.keys())[0]
    return name, modules[name]


def build_netlist(module):
    """
    Parse the Yosys JSON module into a clean netlist representation.
    Handles constant propagation: Yosys represents constants as string "0"/"1"
    in cell connections. We resolve these at parse time, simplifying gates:
      AND(x, 0) = 0,  AND(x, 1) = x
      NOT(0) = 1,     NOT(1) = 0
    This is applied iteratively until no more simplifications are possible.

    Returns:
      - bit_driver: dict mapping bit_id -> ("INPUT",) | ("AND", a_bit, b_bit) | ("NOT", a_bit)
      - bit_name:   dict mapping bit_id -> best human-readable name
      - input_bits:  list of primary input bit ids (ordered)
      - output_bits: list of (port_name_with_index, bit_id) for primary outputs
    """
    ports = module["ports"]
    cells = module["cells"]
    netnames = module["netnames"]

    # We use special sentinel bit IDs for constants.
    # These must not collide with any real Yosys bit ID (which are positive ints).
    CONST0 = "__CONST0__"
    CONST1 = "__CONST1__"

    # ---- Step 1: Identify all primary input bit IDs ----
    input_bits = []
    output_bits = []
    input_bit_set = set()
    output_bit_set = set()
    input_name_override = {}

    for port_name, port_info in ports.items():
        direction = port_info["direction"]
        bits = port_info["bits"]
        upto = port_info.get("upto", 0)
        offset = port_info.get("offset", 0)
        if direction == "input":
            for i, b in enumerate(bits):
                if len(bits) > 1:
                    idx = verilog_bit_index(i, len(bits), offset, upto)
                    label = f"{port_name}[{idx}]"
                else:
                    label = port_name
                if isinstance(b, int):
                    input_bits.append(b)
                    input_bit_set.add(b)
                    input_name_override[b] = sanitize_bench_name(label)
                # If a port bit is constant (unusual but possible), skip it
        elif direction == "output":
            for i, b in enumerate(bits):
                if len(bits) > 1:
                    idx = verilog_bit_index(i, len(bits), offset, upto)
                    label = f"{port_name}[{idx}]"
                else:
                    label = port_name
                # Output bit could be a constant (e.g., unused output tied to 0)
                if isinstance(b, str):
                    b = CONST0 if b == "0" else CONST1
                output_bits.append((label, b))
                if isinstance(b, int):
                    output_bit_set.add(b)

    # ---- Step 2: Build raw bit_driver from cells (before constant prop) ----
    # We use sentinel values for constant connections
    bit_driver = {}
    raw_gates = {}  # bit -> (type, operand1, [operand2]) with constants as sentinels
    unsupported_types = {}

    def resolve_conn(c):
        """Map a Yosys connection value to a bit ID or constant sentinel."""
        if isinstance(c, int):
            return c
        elif c == "0":
            return CONST0
        elif c == "1":
            return CONST1
        elif c == "x" or c == "z":
            # Treat unknown/high-Z as 0 (safe for combinational logic)
            return CONST0
        else:
            print(f"Warning: unexpected connection value '{c}', treating as 0")
            return CONST0

    for cell_name, cell_info in cells.items():
        cell_type = cell_info["type"]
        conns = cell_info["connections"]

        if cell_type == "$_AND_":
            a_bit = resolve_conn(conns["A"][0])
            b_bit = resolve_conn(conns["B"][0])
            y_bit = conns["Y"][0]
            raw_gates[y_bit] = ("AND", a_bit, b_bit)

        elif cell_type == "$_NOT_":
            a_bit = resolve_conn(conns["A"][0])
            y_bit = conns["Y"][0]
            raw_gates[y_bit] = ("NOT", a_bit)

        else:
            unsupported_types[cell_type] = unsupported_types.get(cell_type, 0) + 1

    if unsupported_types:
        types_str = ", ".join(f"{k} ({v})" for k, v in sorted(unsupported_types.items()))
        raise RuntimeError(
            "Unsupported cell types remain after Yosys. "
            f"Found: {types_str}. "
            "Update the Yosys flow to lower these (e.g., add 'techmap; opt;' before 'aigmap')."
        )

    # ---- Step 3: Constant propagation ----
    # known_const maps bit_id -> CONST0 or CONST1
    # alias maps bit_id -> another real bit_id (for AND(x,1)=x cases)
    known_const = {CONST0: CONST0, CONST1: CONST1}
    alias = {}  # bit_id -> real_bit_id (wire pass-through)
    eliminated = 0

    def resolve(b):
        """Resolve a bit through aliases and constants."""
        visited = set()
        while b in alias and b not in visited:
            visited.add(b)
            b = alias[b]
        if b in known_const:
            return known_const[b]
        return b

    # Iterative propagation
    changed = True
    while changed:
        changed = False
        to_remove = []
        for y_bit, gate in raw_gates.items():
            if gate[0] == "AND":
                a = resolve(gate[1])
                b = resolve(gate[2])

                if a == CONST0 or b == CONST0:
                    # AND(x, 0) = 0
                    known_const[y_bit] = CONST0
                    to_remove.append(y_bit)
                    eliminated += 1
                    changed = True
                elif a == CONST1 and b == CONST1:
                    # AND(1, 1) = 1
                    known_const[y_bit] = CONST1
                    to_remove.append(y_bit)
                    eliminated += 1
                    changed = True
                elif a == CONST1:
                    # AND(1, x) = x
                    alias[y_bit] = b
                    to_remove.append(y_bit)
                    eliminated += 1
                    changed = True
                elif b == CONST1:
                    # AND(x, 1) = x
                    alias[y_bit] = a
                    to_remove.append(y_bit)
                    eliminated += 1
                    changed = True
                else:
                    # Update operands to resolved versions
                    raw_gates[y_bit] = ("AND", a, b)

            elif gate[0] == "NOT":
                a = resolve(gate[1])

                if a == CONST0:
                    # NOT(0) = 1
                    known_const[y_bit] = CONST1
                    to_remove.append(y_bit)
                    eliminated += 1
                    changed = True
                elif a == CONST1:
                    # NOT(1) = 0
                    known_const[y_bit] = CONST0
                    to_remove.append(y_bit)
                    eliminated += 1
                    changed = True
                else:
                    raw_gates[y_bit] = ("NOT", a)

        for y in to_remove:
            del raw_gates[y]

    print(f"Constant propagation: eliminated {eliminated} gates")

    # ---- Step 4: Build final bit_driver with resolved operands ----
    for b in input_bits:
        bit_driver[b] = ("INPUT",)

    for y_bit, gate in raw_gates.items():
        if gate[0] == "AND":
            a = resolve(gate[1])
            b = resolve(gate[2])
            bit_driver[y_bit] = ("AND", a, b)
        elif gate[0] == "NOT":
            a = resolve(gate[1])
            bit_driver[y_bit] = ("NOT", a)

    # ---- Step 5: Handle outputs that are constants or aliases ----
    # If an output is driven by a constant, we need a gate to produce it.
    # We create a buffer chain: const0_node = AND(any_input, NOT(any_input)) etc.
    # But simpler: just note which outputs are constant and handle in emit.
    # For now, resolve output bits through aliases.
    resolved_output_bits = []
    const_output_nodes = {}  # label -> CONST0 or CONST1

    for label, b in output_bits:
        rb = resolve(b)
        if rb == CONST0 or rb == CONST1:
            const_output_nodes[label] = rb
            resolved_output_bits.append((label, rb))
        else:
            resolved_output_bits.append((label, rb))

    output_bits = resolved_output_bits

    # ---- Step 6: Build best name for each bit ----
    bit_name = {}           # bit_id -> bench-safe name
    bit_verilog_name = {}   # bit_id -> original Verilog name (unsanitized)

    # Prefer top-level output port labels for naming outputs
    output_name_override = {}
    for label, b in output_bits:
        if isinstance(b, int):
            output_name_override[b] = sanitize_bench_name(label)

    # First pass: assign names from netnames with hide_name=0 (user-visible)
    for net_name, net_info in netnames.items():
        hide = net_info.get("hide_name", 0)
        bits = net_info["bits"]
        upto = net_info.get("upto", 0)
        offset = net_info.get("offset", 0)
        for i, b in enumerate(bits):
            if isinstance(b, int):
                if hide == 0:
                    if len(bits) > 1:
                        idx = verilog_bit_index(i, len(bits), offset, upto)
                        verilog_name = f"{net_name}[{idx}]"
                    else:
                        verilog_name = net_name
                    # Only assign if this bit is still in use (not eliminated)
                    if b in bit_driver or resolve(b) in bit_driver:
                        actual_b = resolve(b)
                        if isinstance(actual_b, int):  # not a constant
                            bit_verilog_name[actual_b] = verilog_name
                            if actual_b not in bit_name:
                                bit_name[actual_b] = sanitize_bench_name(verilog_name)

    # Override output bit names with their port labels
    for b, out_name in output_name_override.items():
        bit_name[b] = out_name

    # Override input bit names with their port labels
    for b, in_name in input_name_override.items():
        bit_name[b] = in_name

    # Second pass: assign names for unnamed bits
    for b in bit_driver:
        if b not in bit_name:
            bit_name[b] = f"n{b}"

    # Also handle any bits referenced by cells but not yet named
    all_referenced = set()
    for b, drv in bit_driver.items():
        all_referenced.add(b)
        if drv[0] == "AND":
            all_referenced.add(drv[1])
            all_referenced.add(drv[2])
        elif drv[0] == "NOT":
            all_referenced.add(drv[1])
    for b in all_referenced:
        if b not in bit_name and isinstance(b, int):
            bit_name[b] = f"n{b}"

    return bit_driver, bit_name, input_bits, output_bits, const_output_nodes


def emit_bench(bit_driver, bit_name, input_bits, output_bits, const_output_nodes):
    """Generate bench file content. Handles constant outputs by creating
    tie-off gates using a primary input (AND(x, NOT(x)) = 0, etc.)."""
    lines = []
    lines.append("# Bench file generated from Yosys JSON (aigmap)")
    lines.append("# Signal names preserved from original Verilog")
    lines.append("")

    CONST0 = "__CONST0__"
    CONST1 = "__CONST1__"

    # If we have constant outputs, we need to synthesize constant nodes
    # using: const0 = AND(pi, NOT(pi)) for some PI, const1 = NOT(const0)
    need_const0 = any(v == CONST0 for v in const_output_nodes.values())
    need_const1 = any(v == CONST1 for v in const_output_nodes.values())

    # Inputs
    for b in input_bits:
        lines.append(f"INPUT({bit_name[b]})")
    lines.append("")

    # Outputs — use the bit_name for non-constant, label for constant
    for label, b in output_bits:
        if b == CONST0 or b == CONST1:
            out_name = sanitize_bench_name(label)
            lines.append(f"OUTPUT({out_name})")
        else:
            lines.append(f"OUTPUT({bit_name[b]})")
    lines.append("")

    # Emit tie-off gates for constant outputs if needed
    if need_const0 or need_const1:
        if input_bits:
            pi_name = bit_name[input_bits[0]]
            if need_const0 or need_const1:
                lines.append(f"__inv_pi = NOT({pi_name})")
                lines.append(f"__const0 = AND({pi_name}, __inv_pi)")
            if need_const1:
                lines.append(f"__const1 = NOT(__const0)")
            lines.append("")

        # Emit assignments for constant outputs (use NOT(NOT(x)) instead of BUF)
        if any(b == CONST0 for _, b in output_bits):
            lines.append("__buf_const0 = NOT(__const0)")
        if any(b == CONST1 for _, b in output_bits):
            lines.append("__buf_const1 = NOT(__const1)")
        for label, b in output_bits:
            out_name = sanitize_bench_name(label)
            if b == CONST0:
                lines.append(f"{out_name} = NOT(__buf_const0)")
            elif b == CONST1:
                lines.append(f"{out_name} = NOT(__buf_const1)")
        lines.append("")

    # Topological sort: emit gates so that inputs of each gate are defined before use
    emitted = set(b for b in input_bits)
    pending = {}  # bit -> driver tuple
    for b, drv in bit_driver.items():
        if drv[0] != "INPUT":
            pending[b] = drv

    # Iterative topological emit
    progress = True
    ordered_gates = []
    while pending and progress:
        progress = False
        to_remove = []
        for b, drv in pending.items():
            deps_met = True
            if drv[0] == "AND":
                if drv[1] not in emitted or drv[2] not in emitted:
                    deps_met = False
            elif drv[0] == "NOT":
                if drv[1] not in emitted:
                    deps_met = False
            if deps_met:
                ordered_gates.append((b, drv))
                emitted.add(b)
                to_remove.append(b)
                progress = True
        for b in to_remove:
            del pending[b]

    if pending:
        print(f"Warning: {len(pending)} gates could not be topologically sorted (possible cycle or missing driver)")
        # Emit them anyway
        for b, drv in pending.items():
            ordered_gates.append((b, drv))

    # Emit gates
    for b, drv in ordered_gates:
        name = bit_name[b]
        if drv[0] == "AND":
            a_name = bit_name[drv[1]]
            b_name = bit_name[drv[2]]
            lines.append(f"{name} = AND({a_name}, {b_name})")
        elif drv[0] == "NOT":
            a_name = bit_name[drv[1]]
            lines.append(f"{name} = NOT({a_name})")

    lines.append("")
    return "\n".join(lines)


def build_mapping(bit_driver, bit_name, input_bits, output_bits, netnames):
    """
    Build sidecar mapping JSON:
    - bench_node_id -> verilog_signal_name (for named signals)
    - Also records which nodes are inputs, outputs, intermediates
    - Records all Verilog names that map to each bit
    """
    # Invert: for each bit, collect all Verilog-visible names
    bit_to_verilog_names = defaultdict(list)
    for net_name, net_info in netnames.items():
        if net_info.get("hide_name", 0) == 0:
            bits = net_info["bits"]
            upto = net_info.get("upto", 0)
            offset = net_info.get("offset", 0)
            for i, b in enumerate(bits):
                if isinstance(b, int):
                    if len(bits) > 1:
                        idx = verilog_bit_index(i, len(bits), offset, upto)
                        vname = f"{net_name}[{idx}]"
                    else:
                        vname = net_name
                    bit_to_verilog_names[b].append(vname)

    input_set = set(input_bits)
    output_set = set(b for _, b in output_bits)

    mapping = {
        "inputs": {},
        "outputs": {},
        "intermediates": {},
        "all_named_nodes": {}
    }

    for b, bench_name in bit_name.items():
        verilog_names = bit_to_verilog_names.get(b, [])
        entry = {
            "bench_name": bench_name,
            "yosys_bit_id": b,
            "verilog_names": verilog_names,
            "gate_type": bit_driver.get(b, ("UNKNOWN",))[0]
        }

        if b in input_set:
            mapping["inputs"][bench_name] = entry
        elif b in output_set:
            mapping["outputs"][bench_name] = entry
        elif verilog_names:
            mapping["intermediates"][bench_name] = entry

        if verilog_names:
            mapping["all_named_nodes"][bench_name] = {
                "verilog_names": verilog_names,
                "bit_id": b,
                "type": "input" if b in input_set else "output" if b in output_set else "gate"
            }

    return mapping


def main():
    parser = argparse.ArgumentParser(description="Convert Yosys JSON (after aigmap) to BENCH format")
    parser.add_argument("json_file", help="Input Yosys JSON file")
    parser.add_argument("--module", "-m", help="Module name (default: first module)", default=None)
    parser.add_argument("--output", "-o", help="Output bench file (default: derived from input)", default=None)
    args = parser.parse_args()

    data = load_yosys_json(args.json_file)
    mod_name, module = pick_module(data, args.module)

    print(f"Processing module: {mod_name}")

    bit_driver, bit_name, input_bits, output_bits, const_output_nodes = build_netlist(module)

    bench_content = emit_bench(bit_driver, bit_name, input_bits, output_bits, const_output_nodes)

    # Determine output paths
    base = args.output if args.output else os.path.splitext(args.json_file)[0]
    if base.endswith(".bench"):
        bench_path = base
        map_path = base.replace(".bench", ".mapping.json")
    else:
        bench_path = base + ".bench"
        map_path = base + ".mapping.json"

    with open(bench_path, "w") as f:
        f.write(bench_content)
    print(f"Wrote bench file: {bench_path}")

    # Build and write mapping
    mapping_data = build_mapping(bit_driver, bit_name, input_bits, output_bits, module["netnames"])
    mapping_data["_meta"] = {
        "source_json": args.json_file,
        "module": mod_name,
        "num_inputs": len(input_bits),
        "num_outputs": len(output_bits),
        "num_gates": sum(1 for d in bit_driver.values() if d[0] != "INPUT"),
        "num_named_intermediates": len(mapping_data["intermediates"])
    }

    with open(map_path, "w") as f:
        json.dump(mapping_data, f, indent=2)
    print(f"Wrote mapping file: {map_path}")

    # Summary
    meta = mapping_data["_meta"]
    print(f"\nSummary:")
    print(f"  Inputs:  {meta['num_inputs']}")
    print(f"  Outputs: {meta['num_outputs']}")
    print(f"  Gates:   {meta['num_gates']}")
    print(f"  Named intermediates: {meta['num_named_intermediates']}")


if __name__ == "__main__":
    main()