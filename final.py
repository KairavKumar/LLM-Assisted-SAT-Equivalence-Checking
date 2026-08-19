"""
final_A.py — SAT-based circuit optimisation via MFFC equivalence collapsing.
             Correctness strategy: NO clause caching across queries.
             Every SAT query regenerates clauses fresh from the current DSU state.
             This eliminates all stale-variable bugs at the cost of O(cone_size)
             work per query instead of O(new_nodes_only).

Imports precomputed_MFFC from mffc.py (must be on sys.path).

Usage
-----
    from final_A import solver

    def my_sat(clauses, n_vars):
        # return True if UNSAT (equivalent), False if SAT
        ...

    opt = solver("miter.bench", my_sat)
    opt.process_pairs([("x1","y1"), ("x2","y2"), ...])
    opt.write_final_cnf("out.cnf")
    opt.print_stats()
"""

import array
import random
from mffc import precomputed_MFFC


_AND = 0
_NOT = 1
_PI  = 2


class solver:

    # ── INIT ─────────────────────────────────────────────────────────────────

    def __init__(self, bench_path: str, sat_fn):
        """
        Parameters
        ----------
        bench_path : str
            Path to AIG .bench file (AND + NOT gates only).
        sat_fn : callable
            sat_fn(clauses: list[tuple[int,...]], n_vars: int) -> bool
            Must return True if UNSAT (nodes equivalent), False if SAT.
        """
        self._sat_fn = sat_fn

        (self._n,
         self._pi_ids,
         self._po_ids,
         self._fanins,
         self._gate_type_list,
         self._n2id,
         self._id2n,
        ) = self._parse(bench_path)

        n = self._n

        self._fanouts: list[list[int]] = [[] for _ in range(n)]
        for u in range(n):
            for fi in self._fanins[u]:
                self._fanouts[fi].append(u)

        self._gtype  = array.array('b', self._gate_type_list)

        self._is_pi  = array.array('b', [0] * n)
        for p in self._pi_ids:
            self._is_pi[p] = 1

        self._is_po  = array.array('b', [0] * n)
        for p in self._po_ids:
            self._is_po[p] = 1

        self._par    = array.array('i', range(n))
        self._rank   = array.array('i', [0] * n)
        self._ignore = array.array('b', [0] * n)

        # sat_var[u] = SAT variable for representative u (0 = not yet assigned)
        self._sat_var  = array.array('i', [0] * n)
        self._next_var = 1

        self._visit_epoch = array.array('i', [0] * n)
        self._epoch       = 1

        # Pre-allocate SAT vars for ALL PIs for consistent numbering.
        for p in self._pi_ids:
            self._alloc_var(p)

        self._mffc_solver = precomputed_MFFC(bench_path)

        self._sim_mask = (1 << 64) - 1
        self._sim_sig  = self._build_random_signatures(seed=0)

        self.n_pairs_checked = 0
        self.n_merged        = 0
        self.n_nodes_removed = 0
        self.n_sim_filtered  = 0
        self.n_sat_calls     = 0

    # ── PARSER ───────────────────────────────────────────────────────────────

    def _parse(self, filepath: str):
        name2id: dict = {}
        id2name: list = []
        nxt = [0]

        def get_id(nm: str) -> int:
            v = name2id.get(nm)
            if v is None:
                v = nxt[0]; name2id[nm] = v; id2name.append(nm); nxt[0] += 1
            return v

        pi_ids: list = []; po_ids: list = []
        out_ids: list = []; fanin_lists: list = []; gtypes: list = []

        with open(filepath) as f:
            for lineno, line in enumerate(f, 1):
                if len(line) < 3 or line[0] == '#':
                    continue
                if '=' in line:
                    eq  = line.index('=')
                    out = line[:eq].strip()
                    rhs = line[eq + 1:].strip()
                    gtype_str = rhs[:rhs.index('(')].strip().upper()
                    assert gtype_str in ('AND', 'NOT'), (
                        f"Line {lineno}: unsupported gate '{gtype_str}'"
                    )
                    lp  = rhs.index('(') + 1
                    rp  = rhs.rindex(')')
                    fis = [get_id(a.strip()) for a in rhs[lp:rp].split(',')]
                    out_ids.append(get_id(out))
                    fanin_lists.append(fis)
                    gtypes.append(_AND if gtype_str == 'AND' else _NOT)
                elif line[0] in 'Ii':
                    s = line.index('(') + 1; e = line.index(')')
                    pi_ids.append(get_id(line[s:e]))
                elif line[0] in 'Oo':
                    s = line.index('(') + 1; e = line.index(')')
                    po_ids.append(get_id(line[s:e]))

        n = nxt[0]
        fanins         = [[] for _ in range(n)]
        gate_type_list = [_PI] * n

        for oid, fis, gt in zip(out_ids, fanin_lists, gtypes):
            fanins[oid]         = fis
            gate_type_list[oid] = gt

        return n, pi_ids, po_ids, fanins, gate_type_list, name2id, id2name

    # ── DSU ──────────────────────────────────────────────────────────────────

    def find(self, u: int) -> int:
        par = self._par
        while par[u] != u:
            par[u] = par[par[u]]
            u = par[u]
        return u

    def _union_keep(self, x: int, y: int, keep: int) -> int:
        rx = self.find(x); ry = self.find(y)
        if rx == ry:
            return self.find(keep)
        rk = self.find(keep)
        ro = ry if rk == rx else rx
        self._par[ro] = rk
        return rk

    # ── SAT VARIABLE ALLOCATION ───────────────────────────────────────────────

    def _alloc_var(self, u: int) -> int:
        rep = self.find(u)
        v = self._sat_var[rep]
        if v == 0:
            v = self._next_var
            self._sat_var[rep] = v
            self._next_var += 1
        return v

    # ── CONE BUILDER ─────────────────────────────────────────────────────────

    def _build_cone(self, roots: list[int]) -> list[int]:
        """
        Iterative post-order DFS. Returns nodes in topological order
        (fanins before fanouts). Stops at PIs and ignored nodes.
        """
        epoch       = self._epoch
        self._epoch += 1

        ve    = self._visit_epoch
        is_pi = self._is_pi
        ign   = self._ignore
        fi    = self._fanins
        par   = self._par

        result:  list[int] = []
        stack:   list      = []
        pending: set[int]  = set()

        def _find(u):
            while par[u] != u:
                par[u] = par[par[u]]
                u = par[u]
            return u

        for r in roots:
            rep = _find(r)
            if ve[rep] != epoch and rep not in pending:
                stack.append((rep, False))
                pending.add(rep)

        while stack:
            u, processed = stack.pop()
            rep = _find(u)

            if ve[rep] == epoch:
                pending.discard(rep)
                continue

            if is_pi[rep] or ign[rep]:
                ve[rep] = epoch
                pending.discard(rep)
                result.append(rep)
                continue

            if processed:
                ve[rep] = epoch
                pending.discard(rep)
                result.append(rep)
            else:
                stack.append((rep, True))
                for fi_u in fi[rep]:
                    fi_rep = _find(fi_u)
                    if ve[fi_rep] != epoch and fi_rep not in pending:
                        stack.append((fi_rep, False))
                        pending.add(fi_rep)

        return result

    # ── TSEITIN ENCODING ─────────────────────────────────────────────────────

    def _encode_node(self, rep: int) -> list:
        """
        Generate Tseitin clauses for rep using the CURRENT DSU state.
        PI and ignored nodes → allocate variable, return [].
        _alloc_var is idempotent so calling this multiple times is safe.
        """
        if self._is_pi[rep] or self._ignore[rep]:
            self._alloc_var(rep)
            return []

        gt = self._gtype[rep]
        g  = self._alloc_var(rep)
        fi = self._fanins[rep]

        if gt == _NOT:
            a = self._alloc_var(self.find(fi[0]))
            return [(g, a), (-g, -a)]

        if len(fi) == 2:
            a = self._alloc_var(self.find(fi[0]))
            b = self._alloc_var(self.find(fi[1]))
            return [(-g, a), (-g, b), (g, -a, -b)]

        fvs = [self._alloc_var(self.find(f)) for f in fi]
        cls = [(-g, fv) for fv in fvs]
        cls.append(tuple([g] + [-fv for fv in fvs]))
        return cls

    def _encode_cone(self, cone: list[int]) -> list:
        """
        Encode every node in cone fresh (no caching). Returns all clauses.
        Because there is no caching, variable references always reflect the
        current DSU state — no stale-variable bugs possible.
        """
        clauses = []
        for rep in cone:
            clauses.extend(self._encode_node(rep))
        return clauses

    # ── RANDOM SIMULATION PREFILTER ──────────────────────────────────────────

    def _topological_order_all_nodes(self) -> list[int]:
        n       = self._n
        fanins  = self._fanins
        fanouts = self._fanouts
        indeg   = [len(fanins[u]) for u in range(n)]
        q       = [u for u in range(n) if indeg[u] == 0]
        order   = []
        head    = 0
        while head < len(q):
            u = q[head]; head += 1
            order.append(u)
            for v in fanouts[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
        return order if len(order) == n else list(range(n))

    def _build_random_signatures(self, seed: int = 0) -> list[int]:
        rng  = random.Random(seed)
        sig  = [0] * self._n
        mask = self._sim_mask

        for p in self._pi_ids:
            sig[p] = rng.getrandbits(64)

        for u in self._topological_order_all_nodes():
            gt = self._gtype[u]
            if gt == _PI:
                if sig[u] == 0 and not self._is_pi[u]:
                    sig[u] = rng.getrandbits(64)
                continue
            fis = self._fanins[u]
            if gt == _NOT:
                sig[u] = (~sig[fis[0]]) & mask
            else:
                v = mask
                for fi_u in fis:
                    v &= sig[fi_u]
                sig[u] = v

        return sig

    # ── MITER CONSTRAINT ──────────────────────────────────────────────────────

    def _make_miter(self, rx: int, ry: int) -> list:
        vx = self._alloc_var(rx)
        vy = self._alloc_var(ry)
        t1 = self._next_var;  self._next_var += 1
        t2 = self._next_var;  self._next_var += 1
        z  = self._next_var;  self._next_var += 1
        return [
            (-t1,  vx      ), (-t1, -vy      ), ( t1, -vx,  vy ),
            (-t2, -vx      ), (-t2,  vy      ), ( t2,  vx, -vy ),
            ( z,  -t1      ), ( z,  -t2      ), (-z,   t1,  t2 ),
            (z,             ),
        ]

    # ── MFFC HELPERS ─────────────────────────────────────────────────────────

    def _mffc_int(self, u: int) -> frozenset:
        name = self._id2n[self.find(u)]
        try:
            names = self._mffc_solver.query(name)
            n2id  = self._n2id
            return frozenset(n2id[nm] for nm in names if nm in n2id)
        except (ValueError, RuntimeError):
            return frozenset({self.find(u)})

    # ── MAIN PROCESSING LOOP ──────────────────────────────────────────────────

    def process_pairs(self, pairs: list[tuple[str, str]]):
        """
        For each candidate pair (x, y):
          1. Simulation pre-filter (64-bit signatures).
          2. Build combined cone from current DSU roots.
          3. Encode cone FRESH (no caching) → current DSU state guaranteed.
          4. Add miter constraint and call SAT.
          5. If UNSAT: DSU merge + MFFC collapse.
        """
        n2id = self._n2id

        for x_name, y_name in pairs:
            self.n_pairs_checked += 1

            x = n2id.get(x_name)
            y = n2id.get(y_name)
            if x is None or y is None:
                continue

            rx = self.find(x)
            ry = self.find(y)
            if rx == ry:
                continue

            if self._sim_sig[rx] != self._sim_sig[ry]:
                self.n_sim_filtered += 1
                continue

            cone = self._build_cone([rx, ry])

            # Fresh encode — reflects current DSU, no stale references possible.
            query_clauses  = self._encode_cone(cone)
            query_clauses += self._make_miter(rx, ry)

            self.n_sat_calls += 1
            is_unsat = self._sat_fn(query_clauses, self._next_var - 1)

            if not is_unsat:
                continue

            self.n_merged += 1

            mx = self._mffc_int(rx)
            my = self._mffc_int(ry)

            if len(mx) >= len(my):
                collapse_set, keep, remove_root = mx, ry, rx
            else:
                collapse_set, keep, remove_root = my, rx, ry

            self._union_keep(remove_root, keep, keep=keep)
            self._alloc_var(keep)

            keep_rep = self.find(keep)
            for u in collapse_set:
                if self.find(u) != keep_rep:
                    if not self._ignore[u]:
                        self._ignore[u] = 1
                        self.n_nodes_removed += 1

    # ── FINAL CNF GENERATION ─────────────────────────────────────────────────

    def write_final_cnf(self, out_path: str) -> tuple:
        """
        Encode the reduced circuit from POs using current DSU state.
        Clauses are generated fresh — consistent with all accumulated merges.
        Returns (n_vars, n_clauses).
        """
        cone        = self._build_cone(self._po_ids)
        all_clauses = self._encode_cone(cone)

        for po in self._po_ids:
            all_clauses.append((self._alloc_var(self.find(po)),))

        n_vars    = self._next_var - 1
        n_clauses = len(all_clauses)

        with open(out_path, 'w') as f:
            f.write(f"p cnf {n_vars} {n_clauses}\n")
            for clause in all_clauses:
                f.write(' '.join(map(str, clause)) + ' 0\n')

        return n_vars, n_clauses

    # ── QUERY HELPERS ─────────────────────────────────────────────────────────

    def fanouts_of(self, node_name: str) -> list[str]:
        u = self._n2id.get(node_name)
        if u is None:
            return []
        return [self._id2n[v] for v in self._fanouts[u]]

    def representative_of(self, node_name: str) -> str:
        u = self._n2id.get(node_name)
        if u is None:
            raise ValueError(f"Node '{node_name}' not found.")
        return self._id2n[self.find(u)]

    def is_ignored(self, node_name: str) -> bool:
        u = self._n2id.get(node_name)
        return u is not None and bool(self._ignore[u])

    # ── STATS ─────────────────────────────────────────────────────────────────

    def print_stats(self):
        print(f"Pairs checked    : {self.n_pairs_checked}")
        print(f"Sim filtered     : {self.n_sim_filtered}")
        print(f"SAT calls        : {self.n_sat_calls}")
        print(f"Merges           : {self.n_merged}")
        print(f"Nodes removed    : {self.n_nodes_removed}")
        print(f"Nodes remaining  : {self._n - self.n_nodes_removed}")
        print(f"SAT vars used    : {self._next_var - 1}")
        print(f"Ignored nodes    : {int(sum(self._ignore))}")
