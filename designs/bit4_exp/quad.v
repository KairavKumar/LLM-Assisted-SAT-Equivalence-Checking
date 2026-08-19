// ========================================================================
// INTERNAL DEPENDENCIES FOR QUADRATIC EXPANSION
// ========================================================================
module qexp_full_adder(input a, b, cin, output s, cout);
    assign s = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule

module qexp_rca #(parameter W=8)(
    input [W-1:0] a, input [W-1:0] b, input cin, 
    output [W-1:0] sum, output cout
);
    wire [W:0] c;
    assign c[0] = cin;
    genvar i;
    generate
        for(i=0; i<W; i=i+1) begin : gen_rca
            qexp_full_adder fa(.a(a[i]), .b(b[i]), .cin(c[i]), .s(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[W];
endmodule

// Carry-Select Adder for faster term accumulation
module qexp_csea #(parameter W=12)(
    input [W-1:0] a, input [W-1:0] b, input cin,
    output [W-1:0] sum, output cout
);
    wire [W/2-1:0] sum_lo; wire cout_lo;
    qexp_rca #(W/2) rca_lo(.a(a[W/2-1:0]), .b(b[W/2-1:0]), .cin(cin), .sum(sum_lo), .cout(cout_lo));

    wire [W/2-1:0] sum_hi0, sum_hi1; wire cout_hi0, cout_hi1;
    qexp_rca #(W/2) rca_hi0(.a(a[W-1:W/2]), .b(b[W-1:W/2]), .cin(1'b0), .sum(sum_hi0), .cout(cout_hi0));
    qexp_rca #(W/2) rca_hi1(.a(a[W-1:W/2]), .b(b[W-1:W/2]), .cin(1'b1), .sum(sum_hi1), .cout(cout_hi1));

    assign sum[W-1:W/2] = cout_lo ? sum_hi1 : sum_hi0;
    assign sum[W/2-1:0]  = sum_lo;
    assign cout = cout_lo ? cout_hi1 : cout_hi0;
endmodule

module qexp_array_mult #(parameter WA=4, WB=4)(
    input [WA-1:0] a, input [WB-1:0] b, output [WA+WB-1:0] p
);
    wire [WA+WB-1:0] partials [WB-1:0];
    wire [WA+WB-1:0] sums [WB:0];
    assign sums[0] = 0;
    genvar i;
    generate
        for(i=0; i<WB; i=i+1) begin : gen_mult_row
            assign partials[i] = b[i] ? ({ {(WB){1'b0}}, a } << i) : 0;
            qexp_rca #(WA+WB) add_row (.a(sums[i]), .b(partials[i]), .cin(1'b0), .sum(sums[i+1]), .cout());
        end
    endgenerate
    assign p = sums[WB];
endmodule

// ========================================================================
// TOP MODULE: THE Q^2 EXPANSION
// ========================================================================
module exp_quadratic_square (
    input [3:0] a, b, c, 
    output [23:0] result
);
    // STEP 1: Compute the 6 base terms using Array Multipliers
    wire [7:0] a2, b2, c2, ab, bc, ca;
    qexp_array_mult #(4,4) m_a2 (.a(a), .b(a), .p(a2));
    qexp_array_mult #(4,4) m_b2 (.a(b), .b(b), .p(b2));
    qexp_array_mult #(4,4) m_c2 (.a(c), .b(c), .p(c2));
    qexp_array_mult #(4,4) m_ab (.a(a), .b(b), .p(ab));
    qexp_array_mult #(4,4) m_bc (.a(b), .b(c), .p(bc));
    qexp_array_mult #(4,4) m_ca (.a(c), .b(a), .p(ca));

    // STEP 2: Shift cross products to multiply by 2 (2ab, 2bc, 2ca)
    // Pad all terms to 12 bits for accumulation
    wire [11:0] t1 = {4'b0, a2};
    wire [11:0] t2 = {4'b0, b2};
    wire [11:0] t3 = {4'b0, c2};
    wire [11:0] t4 = {3'b0, ab, 1'b0}; // ab * 2
    wire [11:0] t5 = {3'b0, bc, 1'b0}; // bc * 2
    wire [11:0] t6 = {3'b0, ca, 1'b0}; // ca * 2

    // STEP 3: Accumulate the 6 terms to form Q using Carry-Select Adders
    wire [11:0] sum1, sum2, sum3, sum4, Q;
    qexp_csea #(12) add1 (.a(t1), .b(t2), .cin(1'b0), .sum(sum1), .cout());
    qexp_csea #(12) add2 (.a(sum1), .b(t3), .cin(1'b0), .sum(sum2), .cout());
    qexp_csea #(12) add3 (.a(sum2), .b(t4), .cin(1'b0), .sum(sum3), .cout());
    qexp_csea #(12) add4 (.a(sum3), .b(t5), .cin(1'b0), .sum(sum4), .cout());
    qexp_csea #(12) add5 (.a(sum4), .b(t6), .cin(1'b0), .sum(Q), .cout());

    // STEP 4: Multiply Q * Q
    qexp_array_mult #(12,12) final_mult (.a(Q), .b(Q), .p(result));

endmodule