# addmult design notes

All addmult variants compute (a + b + c)^4 for 32-bit inputs and produce a 136-bit output.
Each file is self-contained with its own helper adders/multipliers.

## addmult1.v
- RCA-based sum (two ripple stages) to form S = a + b + c.
- Shift-add multipliers with RCA accumulation, using squaring: S^2 then (S^2)^2.

## addmult2.v
- CLA-based sum, with a+b formed by a behavioral + then CLA for +c.
- Shift-add multipliers with CLA accumulation, using squaring: S^2 then (S^2)^2.

## addmult3.v
- CSLA-based sum, with a+b formed by a behavioral + then CSLA for +c.
- Shift-add multipliers with CSLA accumulation, using sequential multiply: S^2, S^3, S^4.

## addmult4.v
- CSK-based sum, with a+b formed by a behavioral + then CSK for +c.
- Shift-add multipliers with CSK accumulation, using squaring: S^2 then (S^2)^2.

## addmult5.v
- CSA compresses a,b,c then CLA resolves to S.
- Booth multiplier for S^2, then CSLA shift-add for (S^2)^2.

## addmult6.v
- Two CSK stages form S.
- CLA shift-add for S^2, then Booth multiplier for (S^2)^2.

## addmult7.v
- RCA sum to form S.
- RCA shift-add for S^2, then Booth multiplier with CLA accumulator for (S^2)^2.
