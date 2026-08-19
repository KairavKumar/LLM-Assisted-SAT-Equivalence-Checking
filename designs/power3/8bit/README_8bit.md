# 8-bit addmult-style design notes

All variants compute `(a + b + c)^3` for 8-bit unsigned inputs and produce a 29-bit output.
Each file is self-contained with its own helper adders/multipliers.

## Common interface
- `input  [7:0] a`
- `input  [7:0] b`
- `input  [7:0] c`
- `output [28:0] y`

## triad_cube_core.v
- Direct decomposition: `ab = a + b`, `s = ab + c`, `sq = s * s`, `y = sq * s`.
- Uses mixed adders: RCA for `a+b`, carry-select for `+c`.
- Uses mixed multipliers: array multiplier for `s^2`, tree multiplier for final `sq*s`.

## sumcube_split.v
- Split-tail decomposition: `bc = b + c`, `s = a + bc`, `sq = s * s`, `y = sq*a + sq*bc`.
- Uses mixed adders: carry-select for `b+c`, RCA for `a+bc`, carry-select for final merge.
- Uses mixed multipliers: tree multiplier for `s^2`, array multiplier for `sq*a`, tree multiplier for `sq*bc`.

## cubic_foldfront.v
- Fold-front decomposition: `bc = b + c`, `s = a + bc`, `q = s*a + s*bc`, `y = q*s`.
- Uses mixed adders: RCA for `b+c`, carry-select for `a+bc`, RCA for merging `q`.
- Uses mixed multipliers: tree multiplier for `s*a`, array multiplier for `s*bc`, array multiplier for final `q*s`.

## distributed_square_cube.v
- Distributed-square decomposition: `ab = a + b`, `s = ab + c`, `sq = s*a + s*b + s*c`, `y = sq*s`.
- Uses mixed adders: carry-select for `a+b`, RCA for `+c`, RCA then carry-select for the two `sq` merges.
- Uses mixed multipliers: array for `s*a`, tree for `s*b`, array for `s*c`, tree for final `sq*s`.

## repeated_cone_cube.v
- Repeated-column decomposition: `col0 = a*a + b*a + c*a`, `col1 = a*b + b*b + c*b`, `col2 = a*c + b*c + c*c`, `sq = col0 + col1 + col2`, `s = a + b + c`, `y = sq*s`.
- Uses mixed adders: RCA then carry-select for `s`, alternating RCA/carry-select in column and final `sq` reductions.
- Uses mixed multipliers: 8x8 product lanes alternate array and tree styles.

## paircone_square_cube.v
- Pair-cone square decomposition: `bc = b + c`, `s = a + bc`, `sq = s*a + s*bc`, `y = sq*s`.
- Uses mixed adders: carry-select for `b+c`, RCA for `a+bc`, carry-select for `sq` merge.
- Uses mixed multipliers: tree multiplier for `s*a`, tree multiplier for `s*bc`, tree multiplier for final `sq*s`.

## paircone_tail_cube.v
- Pair-cone tail decomposition: `ab = a + b`, `s = ab + c`, `sq = s*s`, `y = sq*ab + sq*c`.
- Uses mixed adders: RCA for `a+b`, carry-select for `+c`, RCA for final merge.
- Uses mixed multipliers: tree multiplier for `s^2`, array multiplier for `sq*ab`, tree multiplier for `sq*c`.

## square_split_tail_cube.v
- Square-split tail decomposition: `ab = a + b`, `s = ab + c`, `sq = s*s`, `y = sq*a + sq*b + sq*c`.
- Uses mixed adders: carry-select for `a+b`, RCA for `+c`, carry-select then RCA in the tail merges.
- Uses mixed multipliers: array multiplier for `s^2`, then array / tree / array across the three tail products.

## grouped_tail_cube.v
- Grouped-tail decomposition: `ab = a + b`, `s = ab + c`, `sq = s*ab + s*c`, `y = sq*s`.
- Uses mixed adders: RCA for `a+b`, carry-select for `+c`, RCA for merging `sq`.
- Uses mixed multipliers: tree multiplier for `s*ab`, array multiplier for `s*c`, tree multiplier for final `sq*s`.

## matrix_lane_cube.v
- Matrix-lane decomposition: form nine 8x8 lanes `aa ab ac / ba bb bc / ca cb cc`, reduce row-wise to `r0 r1 r2`, reduce to `sq`, form `s = a + b + c`, then `y = sq*s`.
- Uses mixed adders: row and final reductions alternate carry-select and RCA; `s` uses RCA then carry-select.
- Uses mixed multipliers: the 3x3 lane matrix alternates tree and array implementations across lanes; final `sq*s` uses a tree multiplier.


