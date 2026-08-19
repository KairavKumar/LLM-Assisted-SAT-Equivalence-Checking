import argparse
import os
import shutil
import subprocess
import tempfile
import time

import torch
import torch.nn.functional as F
import deepgate

from bench_utils import get_fanin_nodes, build_miter
from get_embeddings import sanitize_bench_for_deepgate
from final import solver


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Build miter, run DeepGate, reduce with final.py, then SAT."
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
        "--final-cnf",
        default="final_reduced.cnf",
        help="Output CNF path after final.py reduction",
    )
    parser.add_argument(
        "--log",
        default="",
        help="Optional log file path",
    )
    parser.add_argument(
        "--log-result",
        default="log_result.txt",
        help="Summary log with node/clause reductions and SAT time",
    )
    return parser.parse_args()


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


def _log_append(log_lines, msg=""):
    if msg is None:
        msg = ""
    log_lines.append(str(msg))


def main():
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

    parser = deepgate.BenchParser(gate_to_index={"PI": 0, "AND": 1, "NOT": 2, "BUF": 3})
    graph = parser.read_bench(clean_miter_file)

    model = deepgate.Model()
    model.load_pretrained()
    model.eval()
    with torch.no_grad():
        _, embeddings = model(graph)

    equiv_pairs = []
    log_lines = []
    used_cone1_indices = set()
    used_cone2_indices = set()

    print("\n--- DeepGate Submodule Matching Results ---")
    _log_append(log_lines, "DeepGate submodule matching results")

    for sub1, sub2, cone1_nodes, cone2_nodes in cone_pairs:
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
            _log_append(
                log_lines,
                f"Pair: {sub1} vs {sub2} | mean-best cosine = {mean_best:.4f} (empty cone after overlap)",
            )
            _log_append(log_lines, "  -> not equivalent")
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
        _log_append(log_lines, f"Pair: {sub1} vs {sub2} | mean-best cosine = {mean_best:.4f}")
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
                _log_append(log_lines, f"  {node1_name} <-> {node2_name} | score = {sim_score:.4f}")

        if mean_best >= args.equiv_threshold:
            equiv_pairs.append((sub1, sub2))
            _log_append(log_lines, "  -> marked equivalent")
        else:
            _log_append(log_lines, "  -> not equivalent")

        if args.skip_overlap:
            used_cone1_indices.update(cone1_indices)
            used_cone2_indices.update(cone2_indices)

    # Run final.py reduction using the equivalent pairs
    miter_pairs = [(f"{a}_bench1", f"{b}_bench2") for a, b in equiv_pairs]
    opt = solver(miter_file, kissat_sat)
    opt.process_pairs(miter_pairs)
    opt.write_final_cnf(args.final_cnf)
    opt.print_stats()

    # Run SAT on the final CNF and time it
    sat_start = time.perf_counter()
    res = subprocess.run(["kissat", args.final_cnf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sat_elapsed = time.perf_counter() - sat_start
    if res.returncode == 10:
        print("Final CNF: SAT")
        sat_status = "SAT"
    elif res.returncode == 20:
        print("Final CNF: UNSAT")
        sat_status = "UNSAT"
    else:
        raise RuntimeError(f"kissat failed with code {res.returncode}")

    # Parse CNF headers for clause counts
    def _read_cnf_counts(path):
        with open(path, "r") as f:
            for line in f:
                if line.startswith("p cnf"):
                    parts = line.strip().split()
                    return int(parts[2]), int(parts[3])
        raise ValueError(f"Missing CNF header in {path}")

    try:
        final_vars, final_clauses = _read_cnf_counts(args.final_cnf)
    except Exception:
        final_vars, final_clauses = 0, 0

    # Approximate baseline clauses from miter file (AND/NOT only)
    try:
        baseline_solver = solver(miter_file, kissat_sat)
        baseline_solver.write_final_cnf("baseline_miter.cnf")
        base_vars, base_clauses = _read_cnf_counts("baseline_miter.cnf")
    except Exception:
        base_vars, base_clauses = 0, 0

    # Write summary log
    summary_lines = []
    summary_lines.append("summary")
    summary_lines.append(f"pairs_checked\t{opt.n_pairs_checked}")
    summary_lines.append(f"pairs_merged\t{opt.n_merged}")
    summary_lines.append(f"nodes_removed\t{opt.n_nodes_removed}")
    summary_lines.append(f"nodes_remaining\t{opt._n - opt.n_nodes_removed}")
    summary_lines.append(f"baseline_vars\t{base_vars}")
    summary_lines.append(f"baseline_clauses\t{base_clauses}")
    summary_lines.append(f"final_vars\t{final_vars}")
    summary_lines.append(f"final_clauses\t{final_clauses}")
    if base_clauses and final_clauses:
        summary_lines.append(f"clauses_eliminated\t{base_clauses - final_clauses}")
    summary_lines.append(f"sat_status\t{sat_status}")
    summary_lines.append(f"sat_time_sec\t{sat_elapsed:.6f}")

    with open(args.log_result, "w") as f:
        f.write("\n".join(summary_lines) + "\n")

    if args.log:
        with open(args.log, "w") as f:
            f.write("\n".join(log_lines) + "\n")

    for tmp_path in [clean_file1, clean_file2, clean_miter_file]:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    main()
