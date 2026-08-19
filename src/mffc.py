"""
MFFC computation —
Two classes:
  1) demand_MFFC   — doesnt precompute , O(n) worst case query time
     demand MFFC — O(|MFFC|) per query, O(|circuit|) init.

        solver = demand_MFFC("circuit.bench")
        mffc   = solver.query("n42")       # frozenset of str names
        size   = solver.mffc_size("n42")   # int

  2) precomputed_MFFC  — compute all MFFCs in one pass, O(1) query time 
     Precomputed MFFC for all nodes — O(1) query after init.
     Init: O(Σ|MFFC(v)|) 

        solver = precomputed_MFFC("circuit.bench")
        mffc   = solver.query("n42")         # frozenset of str names
        size   = solver.mffc_size("n42")     # int
        table  = solver.size_table()         # {node_name: int}
        all_m  = solver.all_mffcs()          # {node_name: frozenset}

## How to import -- from mffc.py import demand_MFFC, precomputed_MFFC

"""

import array

#  PARSER (AND + NOT only, handles any AND fanin count)

def _parse_bench(filepath: str):
    name2id: dict = {}
    id2name: list = []
    nxt = [0]
    def get_id(nm: str) -> int:
        v = name2id.get(nm)
        if v is None:
            v = nxt[0]; name2id[nm] = v; id2name.append(nm); nxt[0] += 1
        return v

    primary_in_ids: list = []
    primary_out_ids: list = []
    out_ids: list = []
    fanin_lists: list = []

    with open(filepath) as f:
        for lineno, line in enumerate(f, 1):
            if len(line) < 3 or line[0] == '#':
                continue
            if '=' in line:
                eq  = line.index('=')
                out = line[:eq].strip()
                rhs = line[eq + 1:].strip()
                gate_type = rhs[:rhs.index('(')].strip().upper()
                assert gate_type in ('AND', 'NOT'), (
                    f"Line {lineno}: unsupported gate '{gate_type}' — only AND and NOT are allowed in AIG mode.\n  → {line.strip()}"
                )
                lp  = rhs.index('(') + 1
                rp  = rhs.rindex(')')
                fis = tuple(get_id(a.strip()) for a in rhs[lp:rp].split(','))
                out_ids.append(get_id(out))
                fanin_lists.append(fis)
            elif line[0] in 'Ii':
                s = line.index('(') + 1; e = line.index(')')
                primary_in_ids.append(get_id(line[s:e]))
            elif line[0] in 'Oo':
                s = line.index('(') + 1; e = line.index(')')
                primary_out_ids.append(get_id(line[s:e]))

    n = nxt[0]
    fanins = [[] for _ in range(n)]
    for oid, fis in zip(out_ids, fanin_lists):
        fanins[oid] = fis

    return n, primary_in_ids, primary_out_ids, fanins, name2id, id2name


def _build_ref_mask(n, primary_in_ids, primary_out_ids, fanins):
    ref     = array.array('i', [0] * n)
    pi_mask = array.array('b', [0] * n)

    # Mark Primary Inputs
    for p in primary_in_ids:
        pi_mask[p] = 1
        
    # count internal fanouts
    for fis in fanins:
        for fi in fis:
            ref[fi] += 1

    # count Primary Outputs as having an external fanout
    # this prevents them from being absorbed into other MFFCs.
    for po in primary_out_ids:
        ref[po] += 1
        
    return ref, pi_mask

def _compute_levels(n, primary_in_ids, fanins):
    fanout = [[] for _ in range(n)]
    in_deg = array.array('i', [0] * n)
    for u in range(n):
        for fi in fanins[u]:
            fanout[fi].append(u)
            in_deg[u] += 1

    level = array.array('i', [-1] * n)
    queue = list(primary_in_ids)
    for p in primary_in_ids:
        level[p] = 0
    head = 0
    while head < len(queue):
        u = queue[head]; head += 1
        nxt = level[u] + 1
        for v in fanout[u]:
            if nxt > level[v]:
                level[v] = nxt
            in_deg[v] -= 1
            if in_deg[v] == 0:
                queue.append(v)
    max_lvl = max(level)
    buckets = [[] for _ in range(max_lvl + 1)]
    for u in range(n):
        if level[u] >= 0:
            buckets[level[u]].append(u)
    return buckets

def _deref(root, fanins, ref, pi_mask, stack_buf):
    mffc  = []
    _app  = mffc.append
    _push = stack_buf.append
    _pop  = stack_buf.pop
    _ref  = ref
    _pm   = pi_mask
    _fi   = fanins
    _push(root)
    while stack_buf:
        u = _pop()
        _app(u)
        if _pm[u]:
            continue
        fi_list = _fi[u]
        k = len(fi_list)
        if k == 2: # 2-input AND 
            a, b = fi_list
            _ref[a] -= 1
            if _ref[a] == 0 and not _pm[a]:
                _push(a)
            _ref[b] -= 1
            if _ref[b] == 0 and not _pm[b]:
                _push(b)
        elif k == 1: # NOT
            a = fi_list[0]
            _ref[a] -= 1
            if _ref[a] == 0 and not _pm[a]:
                _push(a)
        else: # multi-input AND
            for fi in fi_list:
                _ref[fi] -= 1
                if _ref[fi] == 0 and not _pm[fi]:
                    _push(fi)
    return mffc


def _ref_undo(mffc, fanins, ref, pi_mask):
    _pm  = pi_mask
    _fi  = fanins
    _ref = ref
    for i in range(len(mffc) - 1, -1, -1):
        u = mffc[i]
        if _pm[u]:
            continue
        fi_list = _fi[u]
        k = len(fi_list)
        if k == 2:
            a, b = fi_list
            _ref[a] += 1
            _ref[b] += 1
        elif k == 1:
            _ref[fi_list[0]] += 1
        else:
            for fi in fi_list:
                _ref[fi] += 1


class demand_MFFC:
    """
    On-demand MFFC — O(|MFFC|) per query, O(|circuit|) init.

        solver = demand_MFFC("circuit.bench")
        mffc   = solver.query("n42")       # frozenset of str names
        size   = solver.mffc_size("n42")   # int
        
    """

    def __init__(self, bench_path: str):
        (self._n, self._primary_in_ids, self._primary_out_ids, self._fanins, self._name2id, self._id2name) = _parse_bench(bench_path)
        self._ref, self._pm = _build_ref_mask(self._n, self._primary_in_ids, self._primary_out_ids, self._fanins)
        self._stack: list = []

    def query(self, node_id: str) -> frozenset:
        nid = self._name2id.get(node_id)
        if nid is None:
            raise ValueError(f"Node '{node_id}' not found.")
        assert not self._stack, "stack not empty before deref — internal state corrupt"
        mffc = _deref(nid, self._fanins, self._ref, self._pm, self._stack)
        _ref_undo(mffc, self._fanins, self._ref, self._pm)
        id2n = self._id2name
        return frozenset(id2n[u] for u in mffc)

    def mffc_size(self, node_id: str) -> int:
        nid = self._name2id.get(node_id)
        if nid is None:
            raise ValueError(f"Node '{node_id}' not found.")
        assert not self._stack, "stack not empty before deref — internal state corrupt"
        mffc = _deref(nid, self._fanins, self._ref, self._pm, self._stack)
        _ref_undo(mffc, self._fanins, self._ref, self._pm)
        return len(mffc)

class precomputed_MFFC:
    """
    Precomputed MFFC for all nodes — O(1) query after init.
    Init: O(Σ|MFFC(v)|) 

        solver = precomputed_MFFC("circuit.bench")
        mffc   = solver.query("n42")         # frozenset of str names
        size   = solver.mffc_size("n42")     # int
        table  = solver.size_table()         # {node_name: int}
        all_m  = solver.all_mffcs()          # {node_name: frozenset}

    """

    def __init__(self, bench_path: str):
        (self._n, self._primary_in_ids, self._primary_out_ids, self._fanins, self._name2id, self._id2name) = _parse_bench(bench_path)
        ref, pm  = _build_ref_mask(self._n, self._primary_in_ids, self._primary_out_ids, self._fanins)
        buckets  = _compute_levels(self._n, self._primary_in_ids, self._fanins)

        cache: list = [None] * self._n
        stack_buf: list = []
        for p in self._primary_in_ids:
            cache[p] = [p]

        for bucket in reversed(buckets):
            for u in bucket:
                if pm[u]:
                    continue
                mffc = _deref(u, self._fanins, ref, pm, stack_buf)
                _ref_undo(mffc, self._fanins, ref, pm)
                cache[u] = mffc

        self._cache = cache

    def query(self, node_id: str) -> frozenset:
        nid = self._name2id.get(node_id)
        if nid is None:
            raise ValueError(f"Node '{node_id}' not found.")
        if self._cache[nid] is None:
            raise RuntimeError(f"Node '{node_id}' has no cached MFFC — node may be unreachable from primary inputs.")
        id2n = self._id2name
        return frozenset(id2n[u] for u in self._cache[nid])

    def mffc_size(self, node_id: str) -> int:
        nid = self._name2id.get(node_id)
        if nid is None:
            raise ValueError(f"Node '{node_id}' not found.")
        if self._cache[nid] is None:
            raise RuntimeError(f"Node '{node_id}' has no cached MFFC — node may be unreachable from primary inputs.")
        return len(self._cache[nid])

    def size_table(self) -> dict:
        id2n = self._id2name
        return {id2n[u]: len(self._cache[u])
                for u in range(self._n) if self._cache[u] is not None}

    def all_mffcs(self) -> dict:
        id2n = self._id2name
        return {id2n[u]: frozenset(id2n[v] for v in self._cache[u])
                for u in range(self._n) if self._cache[u] is not None}