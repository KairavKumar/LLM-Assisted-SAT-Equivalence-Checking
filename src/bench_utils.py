"""
Bench file utility functions for boolean function analysis.

Functions:
    get_inputs       - Get primary inputs in a node's fanin cone
    get_truth_table  - Compute truth table as an integer (for small functions), mostly for experimentation
    get_cnf          - Generate CNF in DIMACS format
    extract_cone     - Gets the fanin cone of the supplied node, (read the exception list parameter though)
    build_miter      - Builds the bench miter circuit for the given 2 bench files (intput and output names should be same)
    get_fanin_nodes  - like extract_cone, but only gives all the nodes in the fan-in cone as a list (read the exception list parameter though)

Truth Table Encoding:
    Right-aligned integer. Bit i of the integer = f(input_pattern_i).
    For pattern index i, inputs map to bits of i:
        input_list[0] = MSB of i (most significant)
        input_list[-1] = LSB of i (least significant)

    Example: 2 inputs [A, B], f = AND(A, B)
        Pattern 0 (00): A=0, B=0 -> f=0 -> bit 0 = 0
        Pattern 1 (01): A=0, B=1 -> f=0 -> bit 1 = 0
        Pattern 2 (10): A=1, B=0 -> f=0 -> bit 2 = 0
        Pattern 3 (11): A=1, B=1 -> f=1 -> bit 3 = 1
        tt = 0b1000 = 8

    To query: "what is f when A=1, B=0?"
        pattern = 0b10 = 2
        result = (tt >> 2) & 1  -> 0

    Only PIs in the fanin cone of the function are included (ie not all the inputs). num_inputs tells you 
    how many bits are meaningful: bits 0..(2^num_inputs - 1).

CNF Variable Numbering:
    Variables 1..num_bench_PIs  -> ALL PIs in the bench file (in file order) (not just the PI that are in fanin cone of the function)
    Variables num_bench_PIs+1.. -> internal nodes in the fanin cone
    This global PI numbering makes it easy to combine CNFs from different nodes.
"""


# ---------------------------------------------------------------------------
# Internal: bench file parsing
# ---------------------------------------------------------------------------

def _parse_bench(bench_path):
    """
    Parse a bench file into structured data.

    Returns:
        pi_list:   list of PI names in order of appearance
        po_list:   list of PO names in order of appearance
        gate_defs: dict mapping node_name -> (gate_type_str, [input_names])
    """
    pi_list = []
    po_list = []
    gate_defs = {}

    with open(bench_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if 'INPUT(' in line:
                name = line.split('(', 1)[1].split(')')[0].strip()
                pi_list.append(name)

            elif 'OUTPUT(' in line:
                name = line.split('(', 1)[1].split(')')[0].strip()
                po_list.append(name)

            elif '=' in line:
                lhs, rhs = line.split('=', 1)
                node_name = lhs.strip()
                # strip any leading index added by add_node_index  e.g. "3:G17"
                if ':' in node_name:
                    node_name = node_name.split(':', 1)[1].strip()
                rhs = rhs.strip()
                gate_type = rhs.split('(')[0].strip()
                inputs_str = rhs.split('(', 1)[1].rsplit(')', 1)[0]
                inputs = [x.strip() for x in inputs_str.split(',')]
                gate_defs[node_name] = (gate_type, inputs)

    return pi_list, po_list, gate_defs


def _get_fanin_pis(node_name, pi_set, gate_defs):
    """Return the set of PI names in the fanin cone of node_name."""
    visited = set()
    result = set()
    stack = [node_name]

    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        if node in pi_set:
            result.add(node)
        elif node in gate_defs:
            for inp in gate_defs[node][1]:
                stack.append(inp)

    return result


def _get_fanin_cone_ordered(node_name, pi_set, gate_defs):
    """
    Return internal (non-PI) nodes in the fanin cone, topologically ordered
    (dependencies before dependents).
    """
    visited = set()
    ordered = []

    def dfs(node):
        if node in visited or node in pi_set:
            return
        visited.add(node)
        if node in gate_defs:
            for inp in gate_defs[node][1]:
                dfs(inp)
            ordered.append(node)

    dfs(node_name)
    return ordered


def _eval_gate(gate_type, input_vals):
    """Evaluate a single gate given its input values (0/1 ints)."""
    if gate_type == 'AND':
        return int(all(input_vals))
    elif gate_type == 'NAND':
        return int(not all(input_vals))
    elif gate_type == 'OR':
        return int(any(input_vals))
    elif gate_type == 'NOR':
        return int(not any(input_vals))
    elif gate_type == 'NOT':
        return 1 - input_vals[0]
    elif gate_type == 'XOR':
        return sum(input_vals) % 2
    elif gate_type == 'XNOR':
        return 1 - (sum(input_vals) % 2)
    elif gate_type == 'BUF' or gate_type == 'BUFF':
        return input_vals[0]
    else:
        raise ValueError(f"Unsupported gate type: {gate_type}")


def _evaluate_node(node_name, pi_values, pi_set, gate_defs, memo):
    """
    Recursively evaluate a node given PI assignments.
    
    Args:
        node_name:  name of the node to evaluate
        pi_values:  dict of PI_name -> 0/1
        pi_set:     set of all PI names
        gate_defs:  parsed gate definitions
        memo:       dict for memoization (node_name -> result), shared within 
                    one evaluation pass
    """
    if node_name in memo:
        return memo[node_name]

    if node_name in pi_set:
        val = pi_values.get(node_name, 0)
        memo[node_name] = val
        return val

    if node_name not in gate_defs:
        raise KeyError(f"Node '{node_name}' not found in bench file "
                       f"(not a PI and not a gate)")

    gate_type, inputs = gate_defs[node_name]
    input_vals = [_evaluate_node(inp, pi_values, pi_set, gate_defs, memo)
                  for inp in inputs]
    result = _eval_gate(gate_type, input_vals)
    memo[node_name] = result
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_inputs(bench_path, node_name):
    """
    Get the primary inputs in the fanin cone of a node.

    Args:
        bench_path: path to the .bench file
        node_name:  name of the target node (as it appears in the bench file)

    Returns:
        list of PI names, ordered by their appearance in the bench file.
        If node_name is itself a PI, returns [node_name].
    """
    pi_list, _, gate_defs = _parse_bench(bench_path)
    pi_set = set(pi_list)

    if node_name not in pi_set and node_name not in gate_defs:
        raise KeyError(f"Node '{node_name}' not found in bench file")

    cone_pis = _get_fanin_pis(node_name, pi_set, gate_defs)
    return [pi for pi in pi_list if pi in cone_pis]


def get_truth_table(bench_path, node_name):
    """
    Compute the truth table of a node as an integer.

    Intended for small functions only (4-6 inputs). Only PIs in the fanin 
    cone are included (non-contributing PIs are excluded).

    Encoding:
        Right-aligned. Bit i = f(pattern i).
        Pattern i maps to inputs: input_list[0] is MSB, input_list[-1] is LSB.

    To read a specific entry:
        pattern = 0
        for j, pi in enumerate(input_list):
            if pi_is_high:
                pattern |= 1 << (num_inputs - 1 - j)
        result = (tt >> pattern) & 1

    Args:
        bench_path: path to the .bench file
        node_name:  name of the target node

    Returns:
        tuple of (tt, num_inputs, input_list) where:
            tt:          integer truth table
            num_inputs:  number of inputs (truth table has 2^num_inputs entries)
            input_list:  list of PI names in the order used for encoding
    """
    pi_list, _, gate_defs = _parse_bench(bench_path)
    pi_set = set(pi_list)

    if node_name not in pi_set and node_name not in gate_defs:
        raise KeyError(f"Node '{node_name}' not found in bench file")

    cone_pis = _get_fanin_pis(node_name, pi_set, gate_defs)
    input_list = [pi for pi in pi_list if pi in cone_pis]
    n = len(input_list)

    if n > 20:
        raise ValueError(
            f"Node '{node_name}' has {n} inputs in its fanin cone. "
            f"Truth table would require 2^{n} = {2**n} entries. "
            f"This function is intended for small functions (<=20 inputs)."
        )

    tt = 0
    for pattern in range(1 << n):
        # Build PI assignment for this pattern
        pi_values = {}
        for j, pi in enumerate(input_list):
            # input_list[0] = MSB, input_list[-1] = LSB
            bit_pos = n - 1 - j
            pi_values[pi] = (pattern >> bit_pos) & 1

        memo = {}
        result = _evaluate_node(node_name, pi_values, pi_set, gate_defs, memo)
        if result:
            tt |= (1 << pattern)

    return tt, n, input_list
def extract_cone(bench_path, node_name, is_exception_list=False, exception_list=None):
    """
    Extract a sub-circuit bench file for the fanin cone of node_name.

    Args:
        bench_path:        path to the .bench file
        node_name:         target node (becomes the sole output)
        is_exception_list: if True, nodes in exception_list are treated as PIs
        exception_list:    list/set of node names to treat as pseudo-PIs

    Returns:
        string in bench format containing only the fanin cone
    """
    pi_list, _, gate_defs = _parse_bench(bench_path)
    pi_set = set(pi_list)

    if node_name not in pi_set and node_name not in gate_defs:
        raise KeyError(f"Node '{node_name}' not found in bench file")

    if is_exception_list and exception_list:
        exc_set = set(exception_list)
        # For fanin traversal, treat exception nodes as PIs
        effective_pi_set = pi_set | exc_set
    else:
        exc_set = set()
        effective_pi_set = pi_set

    # --- Fanin PIs (real + pseudo) using the effective PI set ---
    cone_pis = _get_fanin_pis(node_name, effective_pi_set, gate_defs)
    real_pis = [pi for pi in pi_list if pi in cone_pis]
    pseudo_pis = [n for n in cone_pis if n in exc_set]

    # --- Fanin internal nodes using the effective PI set ---
    cone_nodes = _get_fanin_cone_ordered(node_name, effective_pi_set, gate_defs)

    lines = []
    for pi in real_pis:
        lines.append(f"INPUT({pi})")
    for pi in pseudo_pis:
        lines.append(f"INPUT({pi})")
    lines.append(f"OUTPUT({node_name})")
    lines.append("")
    for node in cone_nodes:
        gate_type, inputs = gate_defs[node]
        lines.append(f"{node} = {gate_type}({', '.join(inputs)})")

    return "\n".join(lines) + "\n"

def get_fanin_nodes(bench_path, node_name, is_exception_list=False, exception_list=None):
    """
    Get all intermediate (non-PI) nodes in the fanin cone of node_name.

    Args:
        bench_path:        path to the .bench file
        node_name:         target node (becomes the sole output)
        is_exception_list: if True, nodes in exception_list are treated as PIs
        exception_list:    list/set of node names to treat as pseudo-PIs

    Returns:
        list of internal node names in topological order (dependencies before dependents),
        excluding real PIs and pseudo-PIs
    """
    pi_list, _, gate_defs = _parse_bench(bench_path)
    pi_set = set(pi_list)

    if node_name not in pi_set and node_name not in gate_defs:
        raise KeyError(f"Node '{node_name}' not found in bench file")

    if is_exception_list and exception_list:
        effective_pi_set = pi_set | set(exception_list)
    else:
        effective_pi_set = pi_set

    return _get_fanin_cone_ordered(node_name, effective_pi_set, gate_defs)

def build_miter(bench_path1, bench_path2):
    """
    Build a miter circuit from two bench files (AND/NOT AIG format).

    Naming:
        - PIs are shared (no suffix, same name in both circuits)
        - Internal/output nodes from file 1 get suffix _bench1
        - Internal/output nodes from file 2 get suffix _bench2
        - Miter logic nodes get suffix _miter
        - Single output: miter_out_miter (1 iff any matched output pair differs)

    Outputs are matched by name. XOR and OR are decomposed into AND + NOT.

    Args:
        bench_path1: path to first .bench file
        bench_path2: path to second .bench file

    Returns:
        string in bench format (AND + NOT only)
    """
    pi_list1, po_list1, gate_defs1 = _parse_bench(bench_path1)
    pi_list2, po_list2, gate_defs2 = _parse_bench(bench_path2)

    pi_set1 = set(pi_list1)
    pi_set2 = set(pi_list2)

    # Union of PIs preserving order from file1, then extras from file2
    all_pis = list(pi_list1)
    for p in pi_list2:
        if p not in pi_set1:
            all_pis.append(p)

    lines = []
    for pi in all_pis:
        lines.append(f"INPUT({pi})")
    lines.append("OUTPUT(miter_out_miter)")
    lines.append("")

    # --- Gates from bench1 with _bench1 suffix (PIs stay bare) ---
    for node, (gate_type, inputs) in gate_defs1.items():
        renamed = [inp if inp in pi_set1 else f"{inp}_bench1" for inp in inputs]
        lines.append(f"{node}_bench1 = {gate_type}({', '.join(renamed)})")

    lines.append("")

    # --- Gates from bench2 with _bench2 suffix ---
    for node, (gate_type, inputs) in gate_defs2.items():
        renamed = [inp if inp in pi_set2 else f"{inp}_bench2" for inp in inputs]
        lines.append(f"{node}_bench2 = {gate_type}({', '.join(renamed)})")

    lines.append("")

    # --- Match outputs by name ---
    po_set2 = set(po_list2)
    matched = [po for po in po_list1 if po in po_set2]

    if not matched:
        raise ValueError("No matching outputs found between the two bench files")

    # --- XOR each matched pair using AND + NOT ---
    # XOR(a, b) = NOT(AND(NOT(AND(a, NOT(b))), NOT(AND(NOT(a), b))))
    xor_outs = []
    for po in matched:
        a = po if po in pi_set1 else f"{po}_bench1"
        b = po if po in pi_set2 else f"{po}_bench2"

        lines.append(f"not_b_{po}_miter = NOT({b})")
        lines.append(f"a_notb_{po}_miter = AND({a}, not_b_{po}_miter)")
        lines.append(f"not_a_{po}_miter = NOT({a})")
        lines.append(f"nota_b_{po}_miter = AND(not_a_{po}_miter, {b})")
        lines.append(f"not_anotb_{po}_miter = NOT(a_notb_{po}_miter)")
        lines.append(f"not_notab_{po}_miter = NOT(nota_b_{po}_miter)")
        lines.append(f"and_neg_{po}_miter = AND(not_anotb_{po}_miter, not_notab_{po}_miter)")
        lines.append(f"xor_{po}_miter = NOT(and_neg_{po}_miter)")
        xor_outs.append(f"xor_{po}_miter")

    lines.append("")

    # --- OR all XORs: NOT(AND(NOT(x1), NOT(x2), ...)) ---
    if len(xor_outs) == 1:
        lines.append(f"inv_single_miter = NOT({xor_outs[0]})")
        lines.append(f"miter_out_miter = NOT(inv_single_miter)")
    else:
        neg_names = []
        for xo in xor_outs:
            neg = f"not_{xo}"  # already ends with _miter
            lines.append(f"{neg} = NOT({xo})")
            neg_names.append(neg)
        lines.append(f"and_all_neg_miter = AND({', '.join(neg_names)})")
        lines.append(f"miter_out_miter = NOT(and_all_neg_miter)")

    return "\n".join(lines) + "\n"

def get_cnf(bench_path, node_name, assert_output=True, is_exception_list=False, exception_list=None):
    """
    Generate a CNF formula in DIMACS format for the function at node_name.

    Variable numbering:
        1 .. num_PIs           : all PIs in the bench file (in file order)
        num_PIs+1 .. num_vars  : internal nodes in the fanin cone
                                 (topologically ordered)

    All bench PIs get a variable number even if they don't appear in this 
    node's fanin cone. This makes it easy to combine CNFs from different 
    nodes: the same PI always has the same variable number.

    The CNF encodes the gate-level structure such that any satisfying 
    assignment is a consistent logic evaluation. If assert_output=True,
    a unit clause is added asserting the output node is 1.

    Args:
        bench_path:    path to the .bench file
        node_name:     name of the target node
        assert_output: if True, add a unit clause asserting node_name = 1

    Returns:
        tuple of (dimacs_str, var_map) where:
            dimacs_str: string in DIMACS CNF format
            var_map:    dict mapping node_name -> DIMACS variable number (1-indexed)
    """
    pi_list, _, gate_defs = _parse_bench(bench_path)
    pi_set = set(pi_list)

    if node_name not in pi_set and node_name not in gate_defs:
        raise KeyError(f"Node '{node_name}' not found in bench file")

    if is_exception_list and exception_list:
        exc_list = [n for n in exception_list if n not in pi_set]
        exc_set = set(exc_list)
        effective_pi_set = pi_set | exc_set
    else:
        exc_list = []
        exc_set = set()
        effective_pi_set = pi_set

    # --- Assign variables ---
    # PIs get variables 1..num_PIs (all of them, in bench file order)
    var_map = {}
    for i, pi in enumerate(pi_list):
        var_map[pi] = i + 1

    # Exception nodes (pseudo-PIs) get the next variables
    next_var = len(pi_list) + 1
    for node in exc_list:
        var_map[node] = next_var
        next_var += 1

    # Internal nodes in fanin cone get the next variables
    cone_nodes = _get_fanin_cone_ordered(node_name, effective_pi_set, gate_defs)
    for node in cone_nodes:
        var_map[node] = next_var
        next_var += 1

    num_vars = next_var - 1

    # --- Build clauses ---
    clauses = []
    for node in cone_nodes:
        gate_type, inputs = gate_defs[node]
        c = var_map[node]
        inp_vars = [var_map[inp] for inp in inputs]

        if gate_type == 'AND':
            # C = AND(a1, ..., an)
            # For each ai: (-C | ai)
            # (C | -a1 | ... | -an)
            for a in inp_vars:
                clauses.append([-c, a])
            clauses.append([c] + [-a for a in inp_vars])

        elif gate_type == 'OR':
            # C = OR(a1, ..., an)
            # For each ai: (C | -ai)
            # (-C | a1 | ... | an)
            for a in inp_vars:
                clauses.append([c, -a])
            clauses.append([-c] + list(inp_vars))

        elif gate_type == 'NAND':
            # C = NAND(a1, ..., an) = NOT(AND(...))
            # (-C | -a1 | ... | -an)
            # For each ai: (C | ai)
            clauses.append([-c] + [-a for a in inp_vars])
            for a in inp_vars:
                clauses.append([c, a])

        elif gate_type == 'NOR':
            # C = NOR(a1, ..., an) = NOT(OR(...))
            # For each ai: (-C | -ai)
            # (C | a1 | ... | an)
            for a in inp_vars:
                clauses.append([-c, -a])
            clauses.append([c] + list(inp_vars))

        elif gate_type == 'NOT':
            # C = NOT(A)
            a = inp_vars[0]
            clauses.append([-c, -a])
            clauses.append([c, a])

        elif gate_type == 'BUF' or gate_type == 'BUFF':
            # C = A
            a = inp_vars[0]
            clauses.append([-c, a])
            clauses.append([c, -a])

        elif gate_type == 'XOR':
            # Only 2-input XOR supported
            if len(inp_vars) != 2:
                raise ValueError(
                    f"XOR gate '{node}' has {len(inp_vars)} inputs; "
                    f"only 2-input XOR is supported for CNF conversion"
                )
            a, b = inp_vars
            clauses.append([-c, -a, -b])
            clauses.append([-c, a, b])
            clauses.append([c, -a, b])
            clauses.append([c, a, -b])

        elif gate_type == 'XNOR':
            if len(inp_vars) != 2:
                raise ValueError(
                    f"XNOR gate '{node}' has {len(inp_vars)} inputs; "
                    f"only 2-input XNOR is supported for CNF conversion"
                )
            a, b = inp_vars
            clauses.append([-c, a, -b])
            clauses.append([-c, -a, b])
            clauses.append([c, a, b])
            clauses.append([c, -a, -b])

        else:
            raise ValueError(f"Unsupported gate type '{gate_type}' for CNF "
                             f"conversion at node '{node}'")

    # Assert output
    if assert_output:
        if node_name in pi_set:
            clauses.append([var_map[node_name]])
        else:
            clauses.append([var_map[node_name]])

    # --- Format DIMACS ---
    num_clauses = len(clauses)
    lines = [f"p cnf {num_vars} {num_clauses}"]
    for clause in clauses:
        lines.append(" ".join(str(lit) for lit in clause) + " 0")

    return "\n".join(lines), var_map