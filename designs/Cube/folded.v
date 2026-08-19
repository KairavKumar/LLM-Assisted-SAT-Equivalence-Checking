module cube4_fa(input a, input b, input cin, output sum, output cout);
    assign sum = a ^ b ^ cin;
    assign cout = (a & b) | (cin & (a ^ b));
endmodule

module cube4_rca #(parameter W = 10) (
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
            cube4_fa fa(.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate

    assign cout = c[W];
endmodule

module cube4_iterative_cube (
    input  [7:0] a,
    input  [7:0] b,
    input  [7:0] c,
    output [28:0] y
);
    wire [9:0] ext_a = {2'b00, a};
    wire [9:0] ext_b = {2'b00, b};
    wire [9:0] ext_c = {2'b00, c};

    wire [9:0] sum_ab;
    wire       cout_ab;
    cube4_rca #(10) add_ab(.a(ext_a), .b(ext_b), .cin(1'b0), .sum(sum_ab), .cout(cout_ab));

    wire [9:0] s;
    wire       cout_s;
    cube4_rca #(10) add_c(.a(sum_ab), .b(ext_c), .cin(1'b0), .sum(s), .cout(cout_s));

    wire [19:0] p1 = s * s;
    wire [29:0] p2 = p1 * s;
    assign y = p2[28:0];
endmodule
