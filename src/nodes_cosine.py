import sys
from pathlib import Path

import torch
import torch.nn.functional as F

from get_embeddings import sanitize_bench_for_deepgate


THRESHOLD = 0.99
TOP_K = 10
SHOW_CNF_LINES = 5
MITER_BENCH_NAME = "_tmp_combined_miter.bench"


class Logger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.lines = []

    def log(self, msg=""):
        self.lines.append(str(msg))

    def save(self):
        self.log_path.write_text("\n".join(self.lines) + "\n")


def get_node_names(graph):
    names = []
    for idx in range(graph.num_nodes):
        if hasattr(graph, "node_to_name") and idx in graph.node_to_name:
            names.append(str(graph.node_to_name[idx]).strip())
        else:
            names.append(f"node_{idx}")
    return names


def compute_cosine_matrix(emb1, emb2):
    emb1 = F.normalize(emb1, p=2, dim=1)
    emb2 = F.normalize(emb2, p=2, dim=1)
    return emb1 @ emb2.T


def format_cnf(dimacs_str, max_lines=SHOW_CNF_LINES):
    lines = dimacs_str.strip().splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    kept = lines[:max_lines]
    kept.append(f"... ({len(lines) - max_lines} more lines omitted)")
    return "\n".join(kept)


def node_logic_summary(bench_utils, bench_path: Path, node_name: str):
    dimacs_str, _ = bench_utils.get_cnf(str(bench_path), node_name, assert_output=True)
    return format_cnf(dimacs_str)


def get_non_pi_names(graph):
    pi_idx = set(graph.PIs.detach().cpu().tolist())
    non_pi_names = []
    for i in range(graph.num_nodes):
        if i in pi_idx:
            continue
        if hasattr(graph, "node_to_name") and i in graph.node_to_name:
            non_pi_names.append(str(graph.node_to_name[i]).strip())
    return non_pi_names


def mutual_best_matches(sim_mat, threshold):
    best_j_for_i = torch.argmax(sim_mat, dim=1)
    best_i_for_j = torch.argmax(sim_mat, dim=0)

    pairs = []
    for i in range(sim_mat.shape[0]):
        j = best_j_for_i[i].item()
        if best_i_for_j[j].item() != i:
            continue
        score = sim_mat[i, j].item()
        if score < threshold:
            continue
        pairs.append((i, j, score))

    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs


def rename_for_miter(node_name: str, bench_tag: str):
    return f"{node_name}_{bench_tag}"


def get_miter_indices_for_original_non_pi_nodes(miter_graph, original_non_pi_names, bench_tag: str):
    indices = []

    for name in original_non_pi_names:
        miter_name = rename_for_miter(name, bench_tag)
        if miter_name not in miter_graph.name_to_node:
            raise KeyError(f"Node '{miter_name}' not found in miter graph")
        indices.append(miter_graph.name_to_node[miter_name])

    return indices


def log_similarity_summary(logger, node_names1, node_names2, func_pairs_all, func_pairs_topk,
                           bench1: Path, bench2: Path, log_path: Path):
    logger.log("Functional node similarity summary")
    logger.log(f"bench1: {bench1.name}")
    logger.log(f"bench2: {bench2.name}")
    logger.log(f"log file: {log_path.name}")
    logger.log(f"non-PI nodes in {bench1.stem}: {len(node_names1)}")
    logger.log(f"non-PI nodes in {bench2.stem}: {len(node_names2)}")
    logger.log(f"threshold: {THRESHOLD:.2f}")
    logger.log(f"top_k: {TOP_K}")
    logger.log(f"mutual-best functional matches above threshold: {len(func_pairs_all)}")
    logger.log(f"top-k mutual-best functional matches: {len(func_pairs_topk)}")
    logger.log()


def log_match_details(logger, func_pairs, node_names1, node_names2, func_sim,
                      bench_utils, bench1, bench2):
    logger.log("Top mutual-best non-PI node pairs (functional only)")
    logger.log()

    if not func_pairs:
        logger.log(f"No non-PI node matches found above threshold {THRESHOLD:.2f}.")
        logger.log()
        return

    for rank, (i, j, _) in enumerate(func_pairs, start=1):
        n1 = node_names1[i]
        n2 = node_names2[j]
        f_score = func_sim[i, j].item()

        logger.log(f"[{rank}] {bench1.stem}:{n1}  <-->  {bench2.stem}:{n2}")
        logger.log(f"functional cosine = {f_score:.4f}")
        logger.log()

        logger.log(f"CNF summary for {bench1.stem}:{n1}")
        try:
            logger.log(node_logic_summary(bench_utils, bench1, n1))
        except Exception as e:
            logger.log(f"[could not compute CNF summary: {e}]")
        logger.log()

        logger.log(f"CNF summary for {bench2.stem}:{n2}")
        try:
            logger.log(node_logic_summary(bench_utils, bench2, n2))
        except Exception as e:
            logger.log(f"[could not compute CNF summary: {e}]")
        logger.log()


def print_terminal_pairs(func_pairs_topk, node_names1, node_names2, bench1, bench2):
    if not func_pairs_topk:
        print("No matches found.")
        return

    for i, j, _ in func_pairs_topk:
        print(f"{bench1.stem}:{node_names1[i]}, {bench2.stem}:{node_names2[j]}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python node_cosine_similarity.py <bench1> <bench2>")
        sys.exit(1)

    bench1 = Path(sys.argv[1]).resolve()
    bench2 = Path(sys.argv[2]).resolve()

    if not bench1.exists():
        raise FileNotFoundError(f"Missing bench file: {bench1}")
    if not bench2.exists():
        raise FileNotFoundError(f"Missing bench file: {bench2}")

    analysis_dir = Path(__file__).resolve().parent
    project_root = analysis_dir.parent
    deepgate_repo = project_root / "python-deepgate"
    deepgate_pkg_dir = deepgate_repo / "deepgate"

    sys.path.insert(0, str(deepgate_repo))
    sys.path.insert(0, str(deepgate_pkg_dir))

    import deepgate
    import bench_utils

    log_name = f"{bench1.stem}_{bench2.stem}_similarity.log"
    log_path = analysis_dir / log_name
    miter_bench = analysis_dir / MITER_BENCH_NAME
    logger = Logger(log_path)

    model = deepgate.Model()
    model.load_pretrained()
    model.eval()

    parser = deepgate.BenchParser(gate_to_index={"PI": 0, "AND": 1, "NOT": 2, "BUF": 3})

    clean_bench1 = bench1.with_suffix(".clean.bench")
    clean_bench2 = bench2.with_suffix(".clean.bench")
    sanitize_bench_for_deepgate(str(bench1), str(clean_bench1))
    sanitize_bench_for_deepgate(str(bench2), str(clean_bench2))
    for clean_path in [clean_bench1, clean_bench2]:
        text = clean_path.read_text()
        clean_path.write_text(text.replace("BUFF(", "BUF("))

    graph1 = parser.read_bench(str(clean_bench1))
    graph2 = parser.read_bench(str(clean_bench2))

    non_pi_names1 = get_non_pi_names(graph1)
    non_pi_names2 = get_non_pi_names(graph2)

    miter_text = bench_utils.build_miter(str(clean_bench1), str(clean_bench2))
    miter_bench.write_text(miter_text)
    clean_miter = analysis_dir / (MITER_BENCH_NAME.replace(".bench", "") + ".clean.bench")
    sanitize_bench_for_deepgate(str(miter_bench), str(clean_miter))
    clean_miter.write_text(clean_miter.read_text().replace("BUFF(", "BUF("))

    miter_graph = parser.read_bench(str(clean_miter))

    idx1 = get_miter_indices_for_original_non_pi_nodes(miter_graph, non_pi_names1, "bench1")
    idx2 = get_miter_indices_for_original_non_pi_nodes(miter_graph, non_pi_names2, "bench2")

    with torch.no_grad():
        _, hf_all = model(miter_graph)

    hf1 = hf_all[idx1]
    hf2 = hf_all[idx2]

    func_sim = compute_cosine_matrix(hf1, hf2).cpu()
    func_pairs_all = mutual_best_matches(func_sim, THRESHOLD)
    func_pairs_topk = func_pairs_all[:TOP_K]

    log_similarity_summary(
        logger=logger,
        node_names1=non_pi_names1,
        node_names2=non_pi_names2,
        func_pairs_all=func_pairs_all,
        func_pairs_topk=func_pairs_topk,
        bench1=bench1,
        bench2=bench2,
        log_path=log_path,
    )

    log_match_details(
        logger=logger,
        func_pairs=func_pairs_topk,
        node_names1=non_pi_names1,
        node_names2=non_pi_names2,
        func_sim=func_sim,
        bench_utils=bench_utils,
        bench1=bench1,
        bench2=bench2,
    )

    logger.save()
    print_terminal_pairs(func_pairs_topk, non_pi_names1, non_pi_names2, bench1, bench2)

    for tmp_path in [clean_bench1, clean_bench2, clean_miter]:
        if tmp_path.exists():
            tmp_path.unlink()


if __name__ == "__main__":
    main()