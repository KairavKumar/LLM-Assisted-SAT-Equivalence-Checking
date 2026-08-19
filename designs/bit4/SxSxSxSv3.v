
// --- INTERNAL DEPENDENCIES ---
// Carry-Skip (Bypass) Adder
module seq2_cskip #(parameter W=4)(
    input [W-1:0] a, input [W-1:0] b, input cin, 
    output [W-1:0] sum, output cout
);
    wire [W:0] c;
    assign c[0] = cin;
    genvar i;
    generate
        for(i=0; i<W; i=i+1) begin : gen_rca
            assign sum[i] = a[i] ^ b[i] ^ c[i];
            assign c[i+1] = (a[i] & b[i]) | (c[i] & (a[i] ^ b[i]));
        end
    endgenerate
    
    // Bypass logic: if all bits propagate, skip the ripple chain entirely
    wire p_all = &(a ^ b);
    assign cout = p_all ? cin : c[W];
endmodule

// Reverse-Iterating Accumulator Multiplier
module seq2_reverse_mult #(parameter WA=6, WB=6)(
    input [WA-1:0] a, input [WB-1:0] b, 
    output [WA+WB-1:0] p
);
    reg [WA+WB-1:0] acc;
    integer i;
    always @(*) begin
        acc = 0;
        // Iterates MSB to LSB, chaining partial products downwards.
        // This yields a fundamentally different AIG structure than forward iteration.
        for(i=WB-1; i>=0; i=i-1) begin
            if(b[i]) acc = acc + (a << i);
        end
    end
    assign p = acc;
endmodule

// --- TOP MODULE ---
module seq_flow_cskip_reverse (
    input [3:0] a, b, c, 
    output [23:0] result
);
    // 1. Calculate S = a + b + c sequentially using Carry-Skip logic
    wire [3:0] s1; wire c1;
    seq2_cskip #(4) add1(.a(a), .b(b), .cin(1'b0), .sum(s1), .cout(c1));
    
    wire [4:0] s1_ext = {c1, s1};
    wire [4:0] c_ext = {1'b0, c};
    wire [4:0] s2; wire c2;
    seq2_cskip #(5) add2(.a(s1_ext), .b(c_ext), .cin(1'b0), .sum(s2), .cout(c2));
    
    wire [5:0] S = {c2, s2}; 

    // 2. Sequential Multiplications: (((S * S) * S) * S)
    wire [11:0] S2;
    wire [17:0] S3;
    seq2_reverse_mult #(6, 6)   mult_1 (.a(S), .b(S), .p(S2));
    seq2_reverse_mult #(12, 6)  mult_2 (.a(S2), .b(S), .p(S3));
    seq2_reverse_mult #(18, 6)  mult_3 (.a(S3), .b(S), .p(result));
endmodule
