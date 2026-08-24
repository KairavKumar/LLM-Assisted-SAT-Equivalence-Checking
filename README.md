# Verilog to SAT Reduction via ML-Guided Equivalence Checking

A formal verification pipeline that uses Agentic LLMs and Graph Neural Networks (DeepGate2) to intelligently identify and collapse redundant logic, massively shrinking the final CNF size for SAT solvers.

## Key Highlights

- **Agentic LLM Pipeline:** Uses a two-step retrieval-augmented workflow to intelligently propose functionally equivalent submodule cut-points between hierarchical Verilog RTL and flattened AIG logic.
- **DeepGate2 GNN Filtering:** Rejects false structural matches by evaluating logic cone embeddings via functional cosine similarity, avoiding NP-Hard sub-graph isomorphism checks.
- **MFFC Pruning:** Dynamically collapses redundant variables using localized SAT proofs and Maximum Fanout-Free Cone (MFFC) pruning.
- **Massive Speedups:** Achieves up to **68% runtime reduction** on complex arithmetic datapaths compared to Vanilla SAT solvers.

## 🛠️ Pipeline Architecture

This project is structured as a 4-Stage Funnel:
1. **Normalize:** Translates Verilog into strict AND/NOT BENCH logic via Yosys, preserving human-readable signal names.
2. **Propose:** An Agentic LLM analyzes the graph and proposes specific logic cones for equivalence checking.
3. **Filter:** DeepGate2 filters out bad pairs by comparing functional graph embeddings.
4. **Reduce:** A localized Kissat SAT solver verifies the pairs, and proven MFFC cones are completely pruned before final global CNF generation.

## 📝 Acknowledgements
Course Project for CS 525: FMSV (Group 21)
