// --- TOP MODULE (NO DEPENDENCIES) ---
module arch4_golden_baseline (
    input [3:0] a, b, c, 
    output [23:0] result
);
    wire [5:0] S = a + b + c;
    assign result = S * S * S * S;
endmodule