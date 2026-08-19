// --- INTERNAL DEPENDENCIES ---
// Standard Full Adder and RCA
module sqsq_full_adder(input a, b, cin, output s, cout);
    assign s = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule

module sqsq_rca #(parameter W=4)(
    input [W-1:0] a, input [W-1:0] b, input cin, 
    output [W-1:0] sum, output cout
);
    wire [W:0] c;
    assign c[0] = cin;
    genvar i;
    generate
        for(i=0; i<W; i=i+1) begin : gen_rca
            sqsq_full_adder fa(.a(a[i]), .b(b[i]), .cin(c[i]), .s(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[W];
endmodule

// Pure Structural Array Multiplier
module sqsq_array_mult #(parameter WA=6, WB=6)(
    input [WA-1:0] a, input [WB-1:0] b, output [WA+WB-1:0] p
);
    wire [WA+WB-1:0] partials [WB-1:0];
    wire [WA+WB-1:0] sums [WB:0];
    assign sums[0] = 0;
    genvar i;
    generate
        for(i=0; i<WB; i=i+1) begin : gen_mult_row
            assign partials[i] = b[i] ? ({ {(WB){1'b0}}, a } << i) : 0;
            sqsq_rca #(WA+WB) add_row (
                .a(sums[i]), .b(partials[i]), .cin(1'b0),
                .sum(sums[i+1]), .cout()
            );
        end
    endgenerate
    assign p = sums[WB];
endmodule

// --- TOP MODULE ---
module sqsq_flow_rca_grid (
    input [3:0] a, b, c, 
    output [23:0] result
);
    // 1. Calculate S = a + b + c sequentially using slow RCAs
    wire [3:0] s1; wire c1;
    sqsq_rca #(4) add1(.a(a), .b(b), .cin(1'b0), .sum(s1), .cout(c1));
    
    wire [4:0] s1_ext = {c1, s1};
    wire [4:0] c_ext = {1'b0, c};
    wire [4:0] s2; wire c2;
    sqsq_rca #(5) add2(.a(s1_ext), .b(c_ext), .cin(1'b0), .sum(s2), .cout(c2));
    
    wire [5:0] S = {c2, s2}; 

    // 2. Square of Squares Multiplications: (S^2)^2
    wire [11:0] S2;
    
    // First squaring using a 6x6 Array Multiplier
    sqsq_array_mult #(6, 6) mult_sq1 (.a(S), .b(S), .p(S2));
    
    // Second squaring using a massive 12x12 Array Multiplier grid
    wire [23:0] result_int;
    sqsq_array_mult #(12, 12) mult_sq2 (.a(S2), .b(S2), .p(result_int));
    assign result = result_int;
endmodule