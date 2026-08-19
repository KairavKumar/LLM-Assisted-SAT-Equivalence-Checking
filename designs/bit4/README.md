# bit4 design notes

## behavorial.v
- Single behavioral reference implementation.
- Computes S = a + b + c and then (S * S * S * S) directly.

## SxSxSxS.v
- Ripple-carry additions to form S, then iterative multiplications.
- Uses array multiplier blocks to compute S^2, S^3, S^4.

## S2xS2.v
- Carry-select adders to form S.
- Squares S once to get S^2, then multiplies S^2 by itself for S^4.

## S2xS2v2.v
- Ripple-carry adders to form S, then two squaring steps.
- Uses structural array multipliers for S^2 and (S^2)^2.

## hybrid.v
- Carry-save stage compresses a, b, c then resolves with carry-select adder.
- Mixes array and split multipliers: S^2 (array), S^3 (split), S^4 (array).

## SxSxSxSv2.v
- Carry-lookahead adders to form S.
- Forward-iterating accumulator multipliers for S^2, S^3, S^4.

## SxSxSxSv3.v
- Carry-skip adders to form S.
- Reverse-iterating accumulator multipliers for S^2, S^3, S^4.
