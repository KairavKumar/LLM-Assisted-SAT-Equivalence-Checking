// ========================================================================
// 1. FUNDAMENTAL LOGIC GATES
// ========================================================================
module my_half_adder(input a, b, output s, c);
    assign s = a ^ b;
    assign c = a & b;
endmodule

module my_full_adder(input a, b, cin, output s, cout);
    assign s = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule

// ========================================================================
// 2. THE ADDERS
// ========================================================================

// ADDER TYPE A: Carry-Save Adder (3-inputs down to 2 vectors, NO RIPPLING)
module csa_3in #(parameter W=4)(
    input [W-1:0] a, input [W-1:0] b, input [W-1:0] c, 
    output [W-1:0] save_sum, output [W-1:0] save_carry
);
    genvar i;
    generate
        for(i=0; i<W; i=i+1) begin : gen_csa
            my_full_adder fa(.a(a[i]), .b(b[i]), .cin(c[i]), .s(save_sum[i]), .cout(save_carry[i]));
        end
    endgenerate
endmodule

// ADDER TYPE B: Ripple Carry Adder (Deep, slow, standard path)
module rca #(parameter W=6)(
    input [W-1:0] a, input [W-1:0] b, input cin, 
    output [W-1:0] sum, output cout
);
    wire [W:0] c;
    assign c[0] = cin;
    genvar i;
    generate
        for(i=0; i<W; i=i+1) begin : gen_rca
            my_full_adder fa(.a(a[i]), .b(b[i]), .cin(c[i]), .s(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[W];
endmodule

// ADDER TYPE C: Carry-Select Adder (Calculates both carry options in parallel)
module carry_select_adder_6 (
    input [5:0] a, input [5:0] b, input cin, 
    output [5:0] sum, output cout
);
    wire [2:0] s_low; wire c_low;
    rca #(3) rca_low(.a(a[2:0]), .b(b[2:0]), .cin(cin), .sum(s_low), .cout(c_low));

    wire [2:0] s_high_0, s_high_1; wire c_high_0, c_high_1;
    rca #(3) rca_high_0(.a(a[5:3]), .b(b[5:3]), .cin(1'b0), .sum(s_high_0), .cout(c_high_0));
    rca #(3) rca_high_1(.a(a[5:3]), .b(b[5:3]), .cin(1'b1), .sum(s_high_1), .cout(c_high_1));

    // Mux the output based on the actual carry from the lower half
    assign sum[5:3] = c_low ? s_high_1 : s_high_0;
    assign sum[2:0] = s_low;
    assign cout = c_low ? c_high_1 : c_high_0;
endmodule

// ========================================================================
// 3. THE MULTIPLIERS
// ========================================================================

// MULTIPLIER TYPE A: Standard Array Multiplier (Dense grid of RCAs)
module array_mult #(parameter WA=6, WB=6)(
    input [WA-1:0] a, input [WB-1:0] b, output [WA+WB-1:0] p
);
    wire [WA+WB-1:0] partials [WB-1:0];
    wire [WA+WB-1:0] sums [WB:0];
    assign sums[0] = 0;
    genvar i;
    generate
        for(i=0; i<WB; i=i+1) begin : gen_mult_row
            assign partials[i] = b[i] ? ({ {(WB){1'b0}}, a } << i) : 0;
            rca #(WA+WB) add_row (.a(sums[i]), .b(partials[i]), .cin(1'b0), .sum(sums[i+1]), .cout());
        end
    endgenerate
    assign p = sums[WB];
endmodule

// MULTIPLIER TYPE B: Divide-and-Conquer Split Multiplier
// Breaks A into High and Low halves, multiplies independently, then adds.
// AIG structure looks completely different from Array Mult.
module split_mult_12x6 (
    input [11:0] a, input [5:0] b, output [17:0] p
);
    wire [5:0] a_low = a[5:0];
    wire [5:0] a_high = a[11:6];
    
    wire [11:0] p_low;
    wire [11:0] p_high;
    
    // Instantiate two smaller array multipliers
    array_mult #(6,6) mult_lo (.a(a_low), .b(b), .p(p_low));
    array_mult #(6,6) mult_hi (.a(a_high), .b(b), .p(p_high));
    
    // Shift the high product by 6 bits and add them together
    wire [17:0] p_high_shifted = {p_high, 6'b000000};
    wire [17:0] p_low_extended = {6'b000000, p_low};
    
    // Use an RCA to merge the split paths
    rca #(18) merge_adder (.a(p_high_shifted), .b(p_low_extended), .cin(1'b0), .sum(p), .cout());
endmodule

// ========================================================================
// 4. TOP LEVEL: CARRY-SAVE HYBRID IMPLEMENTATION OF (A+B+C)^4
// ========================================================================
module top_carry_save_hybrid (
    input [3:0] a, b, c, 
    output [23:0] result
);
    // STEP 1: Compress 3 inputs down to 2 vectors instantly using CSA
    wire [3:0] save_sum, save_carry;
    csa_3in #(4) csa_stage(.a(a), .b(b), .c(c), .save_sum(save_sum), .save_carry(save_carry));
    
    // STEP 2: Resolve vectors into final 6-bit Sum 'S' using a Carry-Select Adder
    wire [5:0] op1 = {2'b00, save_sum};
    wire [5:0] op2 = {1'b0, save_carry, 1'b0}; // Shift carry left by 1
    wire [5:0] S;
    carry_select_adder_6 resolve_adder(.a(op1), .b(op2), .cin(1'b0), .sum(S), .cout());

    // STEP 3: Compute S^2 using Multiplier Type A (Array)
    wire [11:0] S2;
    array_mult #(6, 6) mult_stage1 (.a(S), .b(S), .p(S2));
    
    // STEP 4: Compute S^3 using Multiplier Type B (Split/Divide-and-Conquer)
    wire [17:0] S3;
    split_mult_12x6 mult_stage2 (.a(S2), .b(S), .p(S3));
    
    // STEP 5: Compute S^4 using Multiplier Type A again (re-parameterized)
    array_mult #(18, 6) mult_stage3 (.a(S3), .b(S), .p(result));

endmodule