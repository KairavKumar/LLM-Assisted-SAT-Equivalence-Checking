// --- INTERNAL DEPENDENCIES FOR ARCH 2 ---
module arch2_half_adder(input a, b, output s, c);
    assign s = a ^ b;
    assign c = a & b;
endmodule

module arch2_full_adder(input a, b, cin, output s, cout);
    assign s = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule

module arch2_rca #(parameter W=3)(
    input [W-1:0] a, input [W-1:0] b, input cin, 
    output [W-1:0] sum, output cout
);
    wire [W:0] c;
    assign c[0] = cin;
    genvar i;
    generate
        for(i=0; i<W; i=i+1) begin : gen_rca
            arch2_full_adder fa(.a(a[i]), .b(b[i]), .cin(c[i]), .s(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[W];
endmodule

module arch2_csea_6 (
    input [5:0] a, input [5:0] b, input cin, 
    output [5:0] sum, output cout
);
    wire [2:0] s_low; wire c_low;
    arch2_rca #(3) rca_low(.a(a[2:0]), .b(b[2:0]), .cin(cin), .sum(s_low), .cout(c_low));

    wire [2:0] s_high_0, s_high_1; wire c_high_0, c_high_1;
    arch2_rca #(3) rca_high_0(.a(a[5:3]), .b(b[5:3]), .cin(1'b0), .sum(s_high_0), .cout(c_high_0));
    arch2_rca #(3) rca_high_1(.a(a[5:3]), .b(b[5:3]), .cin(1'b1), .sum(s_high_1), .cout(c_high_1));

    assign sum[5:3] = c_low ? s_high_1 : s_high_0;
    assign sum[2:0] = s_low;
    assign cout = c_low ? c_high_1 : c_high_0;
endmodule

// --- TOP MODULE ---
module arch2_csel_square_tree (
    input [3:0] a, b, c, 
    output [23:0] result
);
    wire [5:0] ext_a = {2'b00, a};
    wire [5:0] ext_b = {2'b00, b};
    wire [5:0] ext_c = {2'b00, c};
    
    wire [5:0] sum_ab;
    arch2_csea_6 csea1(.a(ext_a), .b(ext_b), .cin(1'b0), .sum(sum_ab), .cout());
    
    wire [5:0] S;
    arch2_csea_6 csea2(.a(sum_ab), .b(ext_c), .cin(1'b0), .sum(S), .cout());

    // Synthesizer will likely infer a fast Wallace/Booth tree here
    wire [11:0] S2 = S * S;
    wire [23:0] result_int = S2 * S2;
    assign result = result_int;
endmodule