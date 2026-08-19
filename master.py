import argparse
import os
import torch
import torch.nn.functional as F
import deepgate
from bench_utils import get_fanin_nodes, build_miter, get_cnf
from get_embeddings import sanitize_bench_for_deepgate
# Assuming you have a way to load your pre-trained DeepGate model
# from your_deepgate_code import DeepGateModel 

def _parse_args():
    parser = argparse.ArgumentParser(
        description="Build miter, embed nodes with DeepGate, and run n^2 similarity for submodules."
    )
    parser.add_argument("--file1", required=True, help="Path to first .bench file")
    parser.add_argument("--file2", required=True, help="Path to second .bench file")
    parser.add_argument(
        "--sub1",
        required=True,
        help="Comma-separated output node names for submodules in file1",
    )
    parser.add_argument(
        "--sub2",
        required=True,
        help="Comma-separated output node names for submodules in file2",
    )
    parser.add_argument(
        "--min-sim",
        type=float,
        default=0.85,
        help="Minimum cosine similarity to print",
    )
    parser.add_argument(
        "--equiv-threshold",
        type=float,
        default=0.99,
        help="Cosine similarity threshold to treat submodules as equivalent",
    )
    parser.add_argument(
        "--no-skip-overlap",
        action="store_false",
        dest="skip_overlap",
        default=True,
        help="Do not skip nodes already compared in earlier pairs",
    )
    parser.add_argument(
        "--cnf-out",
        default="miter_reduced.cnf",
        help="Output DIMACS CNF path",
    )
    parser.add_argument(
        "--log",
        default="",
        help="Optional log file path",
    )
    return parser.parse_args()


args = _parse_args()
file1 = args.file1
file2 = args.file2

clean_file1 = file1.replace(".bench", ".clean.bench")
clean_file2 = file2.replace(".bench", ".clean.bench")
sanitize_bench_for_deepgate(file1, clean_file1)
sanitize_bench_for_deepgate(file2, clean_file2)
for clean_path in [clean_file1, clean_file2]:
    with open(clean_path, "r") as f:
        text = f.read()
    with open(clean_path, "w") as f:
        f.write(text.replace("BUFF(", "BUF("))
submod1_outputs = [s.strip() for s in args.sub1.split(",") if s.strip()]
submod2_outputs = [s.strip() for s in args.sub2.split(",") if s.strip()]

if len(submod1_outputs) != len(submod2_outputs):
    raise ValueError("--sub1 and --sub2 must have the same number of entries")

cone_pairs = []
for sub1, sub2 in zip(submod1_outputs, submod2_outputs):
    cone1_nodes = get_fanin_nodes(clean_file1, sub1)
    cone2_nodes = get_fanin_nodes(clean_file2, sub2)
    cone_pairs.append((sub1, sub2, cone1_nodes, cone2_nodes))

# --- Step 3: Build the Miter Circuit ---
# This merges both bench files into one big string
miter_bench_string = build_miter(clean_file1, clean_file2)

miter_file = "temp_miter.bench"
with open(miter_file, "w") as f:
    f.write(miter_bench_string)

clean_miter_file = miter_file.replace(".bench", ".clean.bench")
sanitize_bench_for_deepgate(miter_file, clean_miter_file)
with open(clean_miter_file, "r") as f:
    text = f.read()
with open(clean_miter_file, "w") as f:
    f.write(text.replace("BUFF(", "BUF("))

# --- Step 4: Parse with DeepGate's BenchParser ---
parser = deepgate.BenchParser(gate_to_index={"PI": 0, "AND": 1, "NOT": 2, "BUF": 3})
graph = parser.read_bench(clean_miter_file)

# --- Step 5: Get Node Embeddings from DeepGate ---
model = deepgate.Model()
model.load_pretrained()
model.eval()
with torch.no_grad():
    _, embeddings = model(graph)

equiv_pairs = []
log_lines = []
used_cone1_indices = set()
used_cone2_indices = set()

def _log(msg=""):
    if msg is None:
        msg = ""
    log_lines.append(str(msg))

print("\n--- DeepGate Submodule Matching Results ---")
_log("DeepGate submodule matching results")
for sub1, sub2, cone1_nodes, cone2_nodes in cone_pairs:
    # CRITICAL: build_miter() appends "_bench1" and "_bench2" to internal nodes!
    cone1_miter_names = [f"{name}_bench1" for name in cone1_nodes]
    cone2_miter_names = [f"{name}_bench2" for name in cone2_nodes]

    cone1_indices = [graph.name_to_node[name] for name in cone1_miter_names if name in graph.name_to_node]
    cone2_indices = [graph.name_to_node[name] for name in cone2_miter_names if name in graph.name_to_node]

    if args.skip_overlap:
        cone1_indices = [i for i in cone1_indices if i not in used_cone1_indices]
        cone2_indices = [i for i in cone2_indices if i not in used_cone2_indices]

    if not cone1_indices or not cone2_indices:
        mean_best = 0.0
        print(
            f"\nPair: {sub1} vs {sub2} | mean-best cosine = {mean_best:.4f} (empty cone after overlap)"
        )
        _log(
            f"Pair: {sub1} vs {sub2} | mean-best cosine = {mean_best:.4f} (empty cone after overlap)"
        )
        _log("  -> not equivalent")
        if args.skip_overlap:
            used_cone1_indices.update(cone1_indices)
            used_cone2_indices.update(cone2_indices)
        continue

    emb_cone1 = embeddings[cone1_indices]
    emb_cone2 = embeddings[cone2_indices]

    if emb_cone1.numel() and emb_cone2.numel():
        similarities = F.cosine_similarity(emb_cone1.unsqueeze(1), emb_cone2.unsqueeze(0), dim=2)
        max_sim_values, max_sim_indices = torch.max(similarities, dim=1)
        mean_best = max_sim_values.mean().item() if max_sim_values.numel() else 0.0
    else:
        max_sim_values = torch.tensor([])
        max_sim_indices = torch.tensor([], dtype=torch.long)
        mean_best = 0.0

    print(f"\nPair: {sub1} vs {sub2} | mean-best cosine = {mean_best:.4f}")
    _log(f"Pair: {sub1} vs {sub2} | mean-best cosine = {mean_best:.4f}")
    for i, node1_idx in enumerate(cone1_indices):
        best_match_idx_in_cone2 = max_sim_indices[i].item()
        best_match_global_idx = cone2_indices[best_match_idx_in_cone2]

        node1_name = graph.node_to_name[node1_idx]
        node2_name = graph.node_to_name[best_match_global_idx]
        sim_score = max_sim_values[i].item()

        if sim_score >= args.min_sim:
            print(
                f"Submod1 Node: {node1_name:15} | Best Match in Submod2: {node2_name:15} | Score: {sim_score:.4f}"
            )
            _log(
                f"  {node1_name} <-> {node2_name} | score = {sim_score:.4f}"
            )

    if mean_best >= args.equiv_threshold:
        equiv_pairs.append((sub1, sub2))
        _log("  -> marked equivalent")
    else:
        _log("  -> not equivalent")

    if args.skip_overlap:
        used_cone1_indices.update(cone1_indices)
        used_cone2_indices.update(cone2_indices)

# --- Step 6: CNF generation with cone pruning and equality constraints ---
exception_nodes = []
for sub1, sub2 in equiv_pairs:
    exception_nodes.append(f"{sub1}_bench1")
    exception_nodes.append(f"{sub2}_bench2")

dimacs_str, var_map = get_cnf(
    clean_miter_file,
    "miter_out_miter",
    assert_output=True,
    is_exception_list=bool(exception_nodes),
    exception_list=exception_nodes,
)

lines = dimacs_str.strip().splitlines()
if not lines or not lines[0].startswith("p cnf"):
    raise ValueError("Unexpected CNF header format")

header = lines[0].split()
num_vars = int(header[2])
clauses = [line for line in lines[1:] if line.strip()]

for sub1, sub2 in equiv_pairs:
    a = var_map[f"{sub1}_bench1"]
    b = var_map[f"{sub2}_bench2"]
    clauses.append(f"-{a} {b} 0")
    clauses.append(f"{a} -{b} 0")

num_clauses = len(clauses)
cnf_lines = [f"p cnf {num_vars} {num_clauses}"] + clauses

with open(args.cnf_out, "w") as f:
    f.write("\n".join(cnf_lines) + "\n")

print(f"\nEquivalent submodule pairs used for pruning: {len(equiv_pairs)}")
_log("")
_log(f"Equivalent submodule pairs used for pruning: {len(equiv_pairs)}")
for sub1, sub2 in equiv_pairs:
    print(f"  - {sub1} == {sub2}")
    _log(f"  - {sub1} == {sub2}")
print(f"Reduced CNF written to: {args.cnf_out}")
_log(f"Reduced CNF written to: {args.cnf_out}")

if args.log:
    with open(args.log, "w") as f:
        f.write("\n".join(log_lines) + "\n")

for tmp_path in [clean_file1, clean_file2, clean_miter_file]:
    if tmp_path and os.path.exists(tmp_path):
        os.remove(tmp_path)