module cube3_csa10 (
    input  [9:0] a,
    input  [9:0] b,
    input  [9:0] c,
    output [9:0] sum,
    output [9:0] carry
);
    genvar i;
    generate
        for (i = 0; i < 10; i = i + 1) begin : gen_csa
            assign sum[i] = a[i] ^ b[i] ^ c[i];
            assign carry[i] = (a[i] & b[i]) | (a[i] & c[i]) | (b[i] & c[i]);
        end
    endgenerate
endmodule

module cube3_fa(input a, input b, input cin, output sum, output cout);
    assign sum = a ^ b ^ cin;
    assign cout = (a & b) | (a & cin) | (b & cin);
endmodule

module cube3_rca #(parameter W = 5) (
    input  [W-1:0] a,
    input  [W-1:0] b,
    input          cin,
    output [W-1:0] sum,
    output         cout
);
    wire [W:0] c;
    assign c[0] = cin;

    genvar i;
    generate
        for (i = 0; i < W; i = i + 1) begin : gen_rca
            cube3_fa fa(.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate

    assign cout = c[W];
endmodule

module cube3_csel10 (
    input  [9:0] a,
    input  [9:0] b,
    output [9:0] sum
);
    wire [4:0] sum_lo;
    wire       carry_lo;
    cube3_rca #(5) lo(.a(a[4:0]), .b(b[4:0]), .cin(1'b0), .sum(sum_lo), .cout(carry_lo));

    wire [4:0] sum_hi0, sum_hi1;
    wire       carry_hi0, carry_hi1;
    cube3_rca #(5) hi0(.a(a[9:5]), .b(b[9:5]), .cin(1'b0), .sum(sum_hi0), .cout(carry_hi0));
    cube3_rca #(5) hi1(.a(a[9:5]), .b(b[9:5]), .cin(1'b1), .sum(sum_hi1), .cout(carry_hi1));

    assign sum[4:0] = sum_lo;
    assign sum[9:5] = carry_lo ? sum_hi1 : sum_hi0;
endmodule

module cube3_carry_save_hybrid (
    input  [7:0] a,
    input  [7:0] b,
    input  [7:0] c,
    output [28:0] y
);
    wire [9:0] ext_a = {2'b00, a};
    wire [9:0] ext_b = {2'b00, b};
    wire [9:0] ext_c = {2'b00, c};

    wire [9:0] csa_sum;
    wire [9:0] csa_carry;
    cube3_csa10 csa(.a(ext_a), .b(ext_b), .c(ext_c), .sum(csa_sum), .carry(csa_carry));

    wire [9:0] s;
    cube3_csel10 add_final(.a(csa_sum), .b({csa_carry[8:0], 1'b0}), .sum(s));

    wire [19:0] s_sq = s * s;
    wire [29:0] cube_full = s_sq * s;

    assign y = cube_full[28:0];
endmodule
