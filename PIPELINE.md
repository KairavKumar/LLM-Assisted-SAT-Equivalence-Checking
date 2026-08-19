# Project Pipeline (Verilog -> BENCH -> ML Matching -> SAT Reduction)

This document explains the end-to-end workflow implemented in `FMSV_project/`:

1. Convert Verilog designs into AIG-style `.bench` files (AND/NOT only).
2. Identify corresponding "submodule output nodes" between the two designs (often helped by an LLM + the name mapping).
3. Run `master_final.py`:
   - Build a miter circuit.
   - Use a pretrained DeepGate model to match logic cones.
   - Use those matches to drive CNF reduction with a SAT-based optimizer (`final.py`).
   - Solve the final CNF with Kissat and write a summary.

The folder `FMSV_project/results/*/` is used to store per-run inputs (`node1.txt`, `node2.txt`) and outputs (`final_reduced.cnf`, `log_result.txt`, optional `record.txt`).

---

## What You Need Installed / Available

Tools:
- `yosys` (used in `generate_bench.sh`)
- `python3`
- `kissat` (SAT solver used by `master_final.py` and `final.py`)

Python deps:
- `torch`
- `deepgate` (pretrained model + bench parser)

Repo helpers:
- `FMSV_project/set_env.sh` adds local `abc`, `oss-cad-suite/bin` (Yosys), and `kissat/build` to `PATH`.

---

## Stage 1: Verilog -> BENCH (AND/NOT AIG)

### 1.1 Run the bench generator

Script: `FMSV_project/generate_bench.sh`

It runs Yosys with an AIG-focused flow and writes JSON:
- `proc; opt; techmap; opt; flatten; opt; aigmap; opt_clean; write_json ...`

Then it converts JSON to BENCH via:
- `FMSV_project/yosys_json_to_bench.py`

Example:
```bash
cd FMSV_project/results/4th
../../generate_bench.sh ../../designs/Cube/grouped_tail_cube.v grouped_tail_cube
```

Outputs (in the current directory):
- `<design>.json` (Yosys)
- `<design>.bench` (AND/NOT only)
- `<design>.mapping.json` (sidecar name mapping)
- `yosys.log`, `bench.log` (logs)

### 1.2 What `yosys_json_to_bench.py` is doing (key details)

File: `FMSV_project/yosys_json_to_bench.py`

Core behavior:
- Preserves human-readable names when possible (ports and netnames).
- Sanitizes names to be BENCH-safe:
  - `a[3] -> a_3`, `foo.bar -> foo_bar`, etc.
- Ensures the emitted BENCH uses only `AND` and `NOT`.
- Performs constant propagation when parsing the Yosys JSON netlist:
  - Simplifies `AND(x, 0)`, `AND(x, 1)`, `NOT(0)`, `NOT(1)` during netlist build.
- Handles constant outputs by synthesizing tie-offs using a real PI:
  - `__const0 = AND(pi, NOT(pi))`
  - `__const1 = NOT(__const0)`
  - Uses a double-NOT pattern instead of an explicit `BUF`.
- Emits gates in (attempted) topological order, falling back to a warning if something cannot be ordered.

Sidecar mapping:
- Writes `<design>.mapping.json` with:
  - `inputs`, `outputs`, `intermediates` (named internal nets), and `all_named_nodes`.
  - Each entry stores `bench_name`, `yosys_bit_id`, `verilog_names`, and a coarse `gate_type`.
  - `_meta` includes counts for inputs/outputs/gates and how many named intermediates existed.

Why the mapping matters:
- It lets you translate from "Verilog-visible" names to the BENCH node names you must pass into later scripts.
- It is extremely useful if you plan to use an LLM to propose candidate node correspondences (by exposing meaningful net names).

---

## Stage 2: Choose the Submodule Outputs to Compare (node1/node2 lists)

`master_final.py` requires two *aligned* lists:
- `--sub1`: comma-separated node names from bench file 1
- `--sub2`: comma-separated node names from bench file 2

These nodes are treated as "submodule outputs" (roots). For each pair `(sub1, sub2)` it:
- extracts each fan-in cone (a list of nodes feeding that root),
- embeds nodes inside the miter using DeepGate,
- computes similarity between cone nodes,
- and decides if `(sub1, sub2)` should be treated as an "equivalent pair" for reduction.

### 2.1 How you store these lists

Convention used in `FMSV_project/results/<run>/`:
- `node1.txt`: one node per line, for design 1
- `node2.txt`: one node per line, for design 2

To pass them into the script as a comma-separated list:
```bash
--sub1 "$(paste -sd, node1.txt)" --sub2 "$(paste -sd, node2.txt)"
```

### 2.2 Where an LLM fits (practical workflow)

There is no LLM-call code in this repo, but an LLM is useful at this stage:
- Input to LLM: portions of `<design>.mapping.json` for both designs (especially `outputs`, `intermediates`, and `verilog_names`).
- Task: propose which nodes represent the same architectural function (e.g., partial sums, carry chains, pipeline stage outputs).
- Output: a proposed aligned list for `node1.txt` and `node2.txt`.

Then you run the pipeline and validate:
- If final SAT says `UNSAT` for the miter, the two designs are equivalent at the matched outputs.
- If SAT, the lists or the designs differ.

Tip:
- Start with a small number of high-confidence nodes (5-20) rather than hundreds.
- Use the DeepGate similarity prints (or `nodes_cosine.py`) to sanity-check whether your choices are plausible.

---

## Stage 3: Run the End-to-End Flow (`master_final.py`)

Main script: `FMSV_project/master_final.py`

Typical run layout:
```bash
cd FMSV_project
./init_results_run.sh            # creates results/4th (or next) with empty node files
cd results/4th

python3 ../../master_final.py \
  --file1 ../../addmult1.bench \
  --file2 ../../addmult2.bench \
  --sub1 "$(paste -sd, node1.txt)" \
  --sub2 "$(paste -sd, node2.txt)" \
  --final-cnf final_reduced.cnf \
  --log record.txt
```

Important args (defaults shown in code):
- `--min-sim` (default `0.85`): only prints per-node matches above this score.
- `--equiv-threshold` (default `0.99`): decides whether a pair `(sub1, sub2)` is "equivalent" overall.
- `--no-skip-overlap`: if set, disables overlap skipping (by default it tries to avoid re-comparing the same miter nodes across pairs).
- `--final-cnf` (default `final_reduced.cnf`): where the reduced CNF gets written.
- `--log` (default empty): if provided, writes a detailed matching log (you often use `record.txt`).
- `--log-result` (default `log_result.txt`): writes a short tab-separated summary (node/clause reduction + SAT time/status).

### 3.1 What `master_final.py` does internally

1. Sanitizes both `.bench` files for DeepGate.
   - Calls `sanitize_bench_for_deepgate()` from `get_embeddings.py`.
   - Then replaces `BUFF(` with `BUF(` in the sanitized files for parser compatibility.

2. Parses `--sub1/--sub2` into aligned lists.
   - They must have the same number of entries.

3. For each `(sub1, sub2)`:
   - Extract fan-in nodes using `bench_utils.get_fanin_nodes()`.
   - This returns internal nodes in topological order, stopping at PIs.

4. Builds a miter bench:
   - Uses `bench_utils.build_miter(clean_file1, clean_file2)`.
   - Node naming is critical:
     - Shared PIs keep their names.
     - Bench1 internal/outputs get suffix `_bench1`.
     - Bench2 internal/outputs get suffix `_bench2`.
     - Miter logic uses `_miter`.
     - Single final output is `miter_out_miter`.
   - XOR and OR are decomposed into AND/NOT only (so the miter stays in AIG form).

5. Runs pretrained DeepGate to get embeddings on the *miter graph*.
   - `deepgate.BenchParser(gate_to_index={"PI":0,"AND":1,"NOT":2,"BUF":3})`
   - `model = deepgate.Model(); model.load_pretrained(); model.eval()`
   - `_, embeddings = model(graph)`

6. Similarity scoring per pair of cones:
   - Builds cone node indices for each side (after `_bench1/_bench2` renaming).
   - Computes cosine similarities between embeddings:
     - For each node in cone1, finds its best match in cone2.
     - Computes `mean-best` cosine across cone1.
   - If `mean-best >= --equiv-threshold`, marks `(sub1, sub2)` as equivalent.

7. CNF reduction and solving:
   - Converts each equivalent pair into miter node names: `(f"{a}_bench1", f"{b}_bench2")`.
   - Calls the SAT-based optimizer from `final.py`:
     - `opt = solver(miter_file, kissat_sat)`
     - `opt.process_pairs(miter_pairs)`
     - `opt.write_final_cnf(--final-cnf)`
   - Runs Kissat on the final CNF and times it.

8. Baseline comparison:
   - Also generates a baseline CNF (no merges applied) from the same miter:
     - `baseline_solver = solver(miter_file, kissat_sat)`
     - `baseline_solver.write_final_cnf("baseline_miter.cnf")`
   - Reads DIMACS headers to compute clause elimination.

9. Writes `log_result.txt` summary (example keys):
   - `pairs_checked`, `pairs_merged`, `nodes_removed`, `baseline_clauses`, `final_clauses`, `sat_status`, `sat_time_sec`, ...

Temporary files:
- The script creates `.clean.bench` variants and deletes them at the end.

---

## Stage 4: The SAT-Based Reduction Algorithm (`final.py`)

File: `FMSV_project/final.py`

This is the core optimization step: it tries to *merge* equivalent nodes and then *collapse* entire Maximum Fanout-Free Cones (MFFCs) when merges succeed.

### 4.1 Data structures and invariants

Representation:
- The input bench must be in AIG style: only `AND` and `NOT`.
- Nodes are assigned integer IDs; the solver stores:
  - fanins, fanouts
  - PI/PO masks
  - gate types

Union-Find / DSU:
- Maintains node equivalence classes as merges accumulate.
- SAT variable allocation is tied to DSU representatives.

Ignored nodes:
- After collapsing an MFFC, nodes are marked ignored.
- Ignored nodes are treated like "stops" in cone building and are not re-encoded.

### 4.2 Optimization 1: Random simulation prefilter (fast reject)

Before invoking SAT for a candidate pair, `final.py` computes a 64-bit random signature per node:
- Assign random 64-bit values to PIs.
- Propagate through the AIG:
  - `NOT` becomes bitwise negation
  - `AND` becomes bitwise AND across fanins

In `process_pairs()`:
- If the signatures for the two candidate reps differ, the pair is rejected without SAT.
- This is a probabilistic filter (can have collisions), but dramatically reduces SAT calls in practice.

### 4.3 Optimization 2: Fresh cone encoding (correctness-first)

For each SAT query:
- Builds a cone from the two nodes using `_build_cone([rx, ry])` (postorder).
- Encodes the cone using Tseitin clauses via `_encode_cone(cone)`.

Key design choice (explicit in `final.py` docstring):
- No clause caching across queries.
- Every query regenerates clauses from the current DSU state.
- This avoids "stale variable" bugs when representatives change due to merges.

Tradeoff:
- More work per query (re-encode cone every time).
- Much simpler correctness story for repeated merges.

### 4.4 How equivalence is checked (miter constraint)

The solver creates a local miter constraint `z = XOR(x, y)` and asserts `z`:
- It builds XOR using two intermediate terms and a final `z`.
- Adds a unit clause `(z)` to force "x != y".

SAT oracle contract:
- The provided `sat_fn` returns `True` when the query is `UNSAT`.
  - UNSAT under `z` means "no assignment can make x != y", so x and y are equivalent.

`master_final.py` implements `sat_fn` by running Kissat on a temporary DIMACS file:
- Kissat returns `20` for UNSAT and `10` for SAT.

### 4.5 Optimization 3: MFFC collapse after successful merge

MFFC support code:
- `final.py` uses `precomputed_MFFC` from `FMSV_project/mffc.py`.

When a pair is proven equivalent (UNSAT):
- It merges the DSU classes, choosing which representative to keep.
- It computes MFFCs of each root and chooses one collapse set to ignore:
  - It selects the larger MFFC to collapse (so more nodes are eliminated).
- Nodes in the chosen MFFC are marked `ignored` and contribute to `nodes_removed`.

Interpretation:
- Once two roots are equivalent, large regions exclusively feeding them can be treated as redundant and removed from subsequent encoding.
- This can significantly reduce the final CNF size.

### 4.6 Final CNF generation

`write_final_cnf(out.cnf)`:
- Builds a cone from *all POs* using the current DSU + ignored nodes.
- Re-encodes fresh Tseitin constraints.
- Adds unit clauses asserting each PO variable (so the CNF represents the miter output condition being true).

In `master_final.py`, the "baseline" CNF is generated by running the same procedure on a fresh solver with zero merges.

---

## Supporting Tools / Variants

### `get_embeddings.py`
File: `FMSV_project/get_embeddings.py`

Provides `sanitize_bench_for_deepgate()`:
- DeepGate expects strict `A = GATE(B, C)` style lines.
- It crashes on:
  - aliases like `A = B`
  - constants like `A = vdd`
- The sanitizer converts:
  - aliases into `AND(rhs, rhs)` (acts like a buffer)
  - constants into pseudo-inputs via `INPUT(lhs)`

### `nodes_cosine.py` (global similarity exploration)
File: `FMSV_project/nodes_cosine.py`

Purpose:
- Compares *all* non-PI nodes between two benches using DeepGate functional embeddings.
- Finds "mutual best matches" above a threshold (`THRESHOLD = 0.99`).
- Writes a log with:
  - summary stats
  - top matches
  - short CNF summaries for each node via `bench_utils.get_cnf()`

This is useful to:
- bootstrap candidate correspondences,
- sanity-check that your naming / miter construction is correct.

### `run_final.py` (apply `final.py` to an existing miter)
File: `FMSV_project/run_final.py`

Purpose:
- When you already have a miter bench and two aligned node lists, this runs `final.py` directly.
- It can map names to `_bench1/_bench2` variants if you pass unsuffixed names.

---

## Results Folder Convention

`FMSV_project/results/<run>/` typically contains:
- Inputs you edit:
  - `node1.txt`, `node2.txt` (one node per line)
- Outputs produced by the pipeline:
  - `final_reduced.cnf` (reduced CNF after merges + MFFC collapse)
  - `baseline_miter.cnf` (baseline CNF, no merges) (written in the run directory if you run from there)
  - `log_result.txt` (tab-separated metrics)
  - `record.txt` (optional; whatever you pass as `--log`, often includes DeepGate logs and pasted Kissat runs)

Helper:
- `FMSV_project/init_results_run.sh` creates a new run folder and initializes empty `node1.txt/node2.txt/record.txt`.

---

## Common Pitfalls (and why they happen)

- Node naming mismatch:
  - In the miter, internal nodes are suffixed (`_bench1`, `_bench2`).
  - Your `--sub1/--sub2` roots must be names that exist in the *original* bench files; the script itself applies suffixing internally when building cone indices.

- DeepGate parser crashes:
  - Fixed by sanitizing the bench (aliases/constants) and normalizing `BUFF` to `BUF`.

- Too many / low-quality node pairs:
  - If `--equiv-threshold` is too low, you may mark wrong pairs as equivalent and get incorrect reductions.
  - Start strict (`0.99`) and only relax if you have independent validation.

- Overlap handling:
  - By default, `master_final.py` skips nodes already compared for earlier pairs.
  - This prevents one large cone from dominating all comparisons, but it also means later pairs might get "empty" cones.

---

## How To Present This in a PPT (suggested slide framing)

1. Problem: equivalence checking between two designs at scale.
2. Normalize: Verilog -> AIG-style BENCH (Yosys + custom converter + name mapping).
3. Candidate mapping: LLM-assisted alignment of important submodule outputs.
4. ML matching: DeepGate embeddings on a miter graph; cosine similarity and a mean-best score.
5. SAT optimization: `final.py` merges equivalent nodes with:
   - random simulation filter (reduce SAT calls),
   - fresh cone encoding (correctness under DSU merges),
   - MFFC collapse (remove redundant cones).
6. Output: reduced CNF + Kissat result + reduction metrics.
