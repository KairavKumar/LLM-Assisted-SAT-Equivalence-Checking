// ========================================================================
// INTERNAL DEPENDENCIES FOR 15-TERM EXPANSION
// ========================================================================
module poly15_full_adder(input a, b, cin, output s, cout);
    assign s = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule

module poly15_rca #(parameter W=24)(
    input [W-1:0] a, input [W-1:0] b, input cin, 
    output [W-1:0] sum, output cout
);
    wire [W:0] c;
    assign c[0] = cin;
    genvar i;
    generate
        for(i=0; i<W; i=i+1) begin : gen_rca
            poly15_full_adder fa(.a(a[i]), .b(b[i]), .cin(c[i]), .s(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[W];
endmodule

module poly15_array_mult #(parameter WA=8, WB=8)(
    input [WA-1:0] a, input [WB-1:0] b, output [WA+WB-1:0] p
);
    wire [WA+WB-1:0] partials [WB-1:0];
    wire [WA+WB-1:0] sums [WB:0];
    assign sums[0] = 0;
    genvar i;
    generate
        for(i=0; i<WB; i=i+1) begin : gen_mult_row
            assign partials[i] = b[i] ? ({ {(WB){1'b0}}, a } << i) : 0;
            poly15_rca #(WA+WB) add_row (.a(sums[i]), .b(partials[i]), .cin(1'b0), .sum(sums[i+1]), .cout());
        end
    endgenerate
    assign p = sums[WB];
endmodule

// Helper to structurally multiply a 16-bit value by a hardcoded constant 6
// x * 6  = (x * 4) + (x * 2) = (x << 2) + (x << 1)
module poly15_mult_by_6 (input [15:0] x, output [23:0] res);
    wire [23:0] shift2 = {6'b0, x, 2'b00};
    wire [23:0] shift1 = {7'b0, x, 1'b0};
    poly15_rca #(24) adder (.a(shift2), .b(shift1), .cin(1'b0), .sum(res), .cout());
endmodule

// Helper to structurally multiply a 16-bit value by a hardcoded constant 12
// x * 12 = (x * 8) + (x * 4) = (x << 3) + (x << 2)
module poly15_mult_by_12 (input [15:0] x, output [23:0] res);
    wire [23:0] shift3 = {5'b0, x, 3'b000};
    wire [23:0] shift2 = {6'b0, x, 2'b00};
    poly15_rca #(24) adder (.a(shift3), .b(shift2), .cin(1'b0), .sum(res), .cout());
endmodule

// ========================================================================
// TOP MODULE: THE 15-TERM BRUTE FORCE
// ========================================================================
module exp_poly15_bruteforce (
    input [3:0] a, b, c, 
    output [23:0] result
);
    // 1. BASE SQUARES AND CROSS PRODUCTS
    wire [7:0] a2, b2, c2, ab, bc, ca;
    poly15_array_mult #(4,4) m_a2 (.a(a), .b(a), .p(a2));
    poly15_array_mult #(4,4) m_b2 (.a(b), .b(b), .p(b2));
    poly15_array_mult #(4,4) m_c2 (.a(c), .b(c), .p(c2));
    poly15_array_mult #(4,4) m_ab (.a(a), .b(b), .p(ab));
    poly15_array_mult #(4,4) m_bc (.a(b), .b(c), .p(bc));
    poly15_array_mult #(4,4) m_ca (.a(c), .b(a), .p(ca));

    // 2. GENERATE ALL 15 EXPANDED TERMS
    wire [23:0] term [0:14];

    // Coeff 1: a^4, b^4, c^4
    wire [15:0] a4, b4, c4;
    poly15_array_mult #(8,8) m_a4 (.a(a2), .b(a2), .p(a4));
    poly15_array_mult #(8,8) m_b4 (.a(b2), .b(b2), .p(b4));
    poly15_array_mult #(8,8) m_c4 (.a(c2), .b(c2), .p(c4));
    assign term[0] = {8'b0, a4};
    assign term[1] = {8'b0, b4};
    assign term[2] = {8'b0, c4};

    // Coeff 4: 4(a^3b, ab^3, a^3c, ac^3, b^3c, bc^3) -> shift left by 2
    wire [15:0] a3b, ab3, a3c, ac3, b3c, bc3;
    poly15_array_mult #(8,8) m_a3b (.a(a2), .b(ab), .p(a3b));
    poly15_array_mult #(8,8) m_ab3 (.a(ab), .b(b2), .p(ab3));
    poly15_array_mult #(8,8) m_a3c (.a(a2), .b(ca), .p(a3c));
    poly15_array_mult #(8,8) m_ac3 (.a(ca), .b(c2), .p(ac3));
    poly15_array_mult #(8,8) m_b3c (.a(b2), .b(bc), .p(b3c));
    poly15_array_mult #(8,8) m_bc3 (.a(bc), .b(c2), .p(bc3));
    assign term[3] = {6'b0, a3b, 2'b00};
    assign term[4] = {6'b0, ab3, 2'b00};
    assign term[5] = {6'b0, a3c, 2'b00};
    assign term[6] = {6'b0, ac3, 2'b00};
    assign term[7] = {6'b0, b3c, 2'b00};
    assign term[8] = {6'b0, bc3, 2'b00};

    // Coeff 6: 6(a^2b^2, a^2c^2, b^2c^2)
    wire [15:0] a2b2, a2c2, b2c2;
    poly15_array_mult #(8,8) m_a2b2 (.a(a2), .b(b2), .p(a2b2));
    poly15_array_mult #(8,8) m_a2c2 (.a(a2), .b(c2), .p(a2c2));
    poly15_array_mult #(8,8) m_b2c2 (.a(b2), .b(c2), .p(b2c2));
    poly15_mult_by_6 m6_1 (.x(a2b2), .res(term[9]));
    poly15_mult_by_6 m6_2 (.x(a2c2), .res(term[10]));
    poly15_mult_by_6 m6_3 (.x(b2c2), .res(term[11]));

    // Coeff 12: 12(a^2bc, ab^2c, abc^2)
    wire [15:0] a2bc, ab2c, abc2;
    poly15_array_mult #(8,8) m_a2bc (.a(a2), .b(bc), .p(a2bc));
    poly15_array_mult #(8,8) m_ab2c (.a(b2), .b(ca), .p(ab2c)); 
    poly15_array_mult #(8,8) m_abc2 (.a(c2), .b(ab), .p(abc2));
    poly15_mult_by_12 m12_1 (.x(a2bc), .res(term[12]));
    poly15_mult_by_12 m12_2 (.x(ab2c), .res(term[13]));
    poly15_mult_by_12 m12_3 (.x(abc2), .res(term[14]));

    // 3. STRUCTURAL ACCUMULATOR (Add all 15 terms sequentially)
    wire [23:0] sums [0:14];
    assign sums[0] = term[0];
    
    genvar i;
    generate
        for(i=0; i<14; i=i+1) begin : gen_accumulation
            poly15_rca #(24) acc_stage (
                .a(sums[i]), 
                .b(term[i+1]), 
                .cin(1'b0), 
                .sum(sums[i+1]), 
                .cout()
            );
        end
    endgenerate

    assign result = sums[14];

endmodule