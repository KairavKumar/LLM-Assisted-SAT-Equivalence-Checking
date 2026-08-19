# exp design notes

All exp variants compute (a + b + c)^4 using expanded forms (not direct S then power).
Each file is self-contained and uses explicit adder/multiplier modules for mapping.

## exp1.v
- Full multinomial expansion with all a^4, b^4, c^4 and cross terms.
- Mixes RCA/CLA/CSLA/CSK adders and multipliers throughout the tree.

## exp2.v
- Uses (a^2+b^2+c^2+2ab+2ac+2bc)^2 identity.
- RCA/CLA/CSK adders build the inner sum, CLA multiplier for squaring.

## exp3.v
- Binomial expansion with d = b + c.
- CSLA for d, mixed multipliers for powers, and varied adders for term sum.

## exp4.v
- Binomial expansion with e = a + b.
- CSK/CLA adders for sums, mixed multipliers for e and c powers.

## exp5.v
- Builds (a+b+c)^2 from pairwise squares, then squares again.
- Uses explicit subtractors via adders (two's complement) and mixed multipliers.

## exp6.v
- Uses p = a^2+b^2+c^2 and q = ab+bc+ca, then p^2 + 4pq + 4q^2.
- Mixed adder styles for p/q and mixed multipliers for p^2, q^2, pq.
