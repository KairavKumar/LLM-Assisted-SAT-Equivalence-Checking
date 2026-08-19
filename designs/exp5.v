// exp5: build (a+b+c)^2 from pairwise squares, then square, with modules.
module exp5 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [135:0] y
);
    wire [32:0] ab;
    wire [32:0] bc;
    wire [32:0] ca;
    exp5_adder_rca #(33) add_ab (.a({1'b0, a}), .b({1'b0, b}), .cin(1'b0), .sum(ab), .cout());
    exp5_adder_csk #(33) add_bc (.a({1'b0, b}), .b({1'b0, c}), .cin(1'b0), .sum(bc), .cout());
    exp5_adder_rca #(33) add_ca (.a({1'b0, c}), .b({1'b0, a}), .cin(1'b0), .sum(ca), .cout());

    wire [65:0] ab2;
    wire [65:0] bc2;
    wire [65:0] ca2;
    exp5_mult_rca  #(33, 33) mul_ab2 (.a(ab), .b(ab), .product(ab2));
    exp5_mult_csla #(33, 33) mul_bc2 (.a(bc), .b(bc), .product(bc2));
    exp5_mult_rca  #(33, 33) mul_ca2 (.a(ca), .b(ca), .product(ca2));

    wire [63:0] a2;
    wire [63:0] b2;
    wire [63:0] c2;
    exp5_mult_rca #(32, 32) mul_a2 (.a(a), .b(a), .product(a2));
    exp5_mult_rca #(32, 32) mul_b2 (.a(b), .b(b), .product(b2));
    exp5_mult_rca #(32, 32) mul_c2 (.a(c), .b(c), .product(c2));

    wire [67:0] ab2e = {2'b0, ab2};
    wire [67:0] bc2e = {2'b0, bc2};
    wire [67:0] ca2e = {2'b0, ca2};
    wire [67:0] a2e = {4'b0, a2};
    wire [67:0] b2e = {4'b0, b2};
    wire [67:0] c2e = {4'b0, c2};

    wire [67:0] s1;
    wire [67:0] s2;
    wire [67:0] s3;
    wire [67:0] s4;
    wire [67:0] s5;
    exp5_adder_rca #(68) add_s1 (.a(ab2e), .b(bc2e), .cin(1'b0), .sum(s1), .cout());
    exp5_adder_csk #(68) add_s2 (.a(s1), .b(ca2e), .cin(1'b0), .sum(s2), .cout());

    exp5_sub_rca #(68) sub_a2 (.a(s2), .b(a2e), .sum(s3));
    exp5_sub_csk #(68) sub_b2 (.a(s3), .b(b2e), .sum(s4));
    exp5_sub_rca #(68) sub_c2 (.a(s4), .b(c2e), .sum(s5));

    exp5_mult_csla #(68, 68) mul_s2 (.a(s5), .b(s5), .product(y));
endmodule

module exp5_mult_rca #(parameter AW = 32, parameter BW = 32) (
    input  [AW-1:0] a,
    input  [BW-1:0] b,
    output [AW+BW-1:0] product
);
    localparam PW = AW + BW;
    wire [PW-1:0] acc [0:AW];
    assign acc[0] = {PW{1'b0}};
    genvar i;
    generate
        for (i = 0; i < AW; i = i + 1) begin : gen_acc
            wire [PW-1:0] pp;
            assign pp = a[i] ? ({ { (PW-BW){1'b0} }, b } << i) : {PW{1'b0}};
            exp5_adder_rca #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp5_mult_csla #(parameter AW = 32, parameter BW = 32) (
    input  [AW-1:0] a,
    input  [BW-1:0] b,
    output [AW+BW-1:0] product
);
    localparam PW = AW + BW;
    wire [PW-1:0] acc [0:AW];
    assign acc[0] = {PW{1'b0}};
    genvar i;
    generate
        for (i = 0; i < AW; i = i + 1) begin : gen_acc
            wire [PW-1:0] pp;
            assign pp = a[i] ? ({ { (PW-BW){1'b0} }, b } << i) : {PW{1'b0}};
            exp5_adder_csk #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp5_adder_rca #(parameter W = 32) (
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
        for (i = 0; i < W; i = i + 1) begin : gen_fa
            exp5_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[W];
endmodule

module exp5_adder_csk #(parameter W = 32) (
    input  [W-1:0] a,
    input  [W-1:0] b,
    input          cin,
    output [W-1:0] sum,
    output         cout
);
    localparam PAD = ((W + 3) / 4) * 4;
    localparam EXTRA = PAD - W;
    wire [PAD-1:0] a_pad = { {EXTRA{1'b0}}, a };
    wire [PAD-1:0] b_pad = { {EXTRA{1'b0}}, b };
    wire [PAD-1:0] sum_pad;
    wire [PAD/4:0] c_block;
    assign c_block[0] = cin;
    genvar i;
    generate
        for (i = 0; i < PAD/4; i = i + 1) begin : gen_csk4
            exp5_csk4 u_csk4 (
                .a(a_pad[i*4 +: 4]),
                .b(b_pad[i*4 +: 4]),
                .cin(c_block[i]),
                .sum(sum_pad[i*4 +: 4]),
                .cout(c_block[i+1])
            );
        end
    endgenerate
    assign sum = sum_pad[W-1:0];
    assign cout = c_block[PAD/4];
endmodule

module exp5_sub_rca #(parameter W = 32) (
    input  [W-1:0] a,
    input  [W-1:0] b,
    output [W-1:0] sum
);
    wire cout;
    exp5_adder_rca #(W) u_sub (.a(a), .b(~b), .cin(1'b1), .sum(sum), .cout(cout));
endmodule

module exp5_sub_csk #(parameter W = 32) (
    input  [W-1:0] a,
    input  [W-1:0] b,
    output [W-1:0] sum
);
    wire cout;
    exp5_adder_csk #(W) u_sub (.a(a), .b(~b), .cin(1'b1), .sum(sum), .cout(cout));
endmodule

module exp5_csk4 (
    input  [3:0] a,
    input  [3:0] b,
    input        cin,
    output [3:0] sum,
    output       cout
);
    wire [3:0] p;
    wire [4:0] c;
    wire       block_prop;
    wire       ripple_cout;
    assign p = a ^ b;
    assign c[0] = cin;
    genvar i;
    generate
        for (i = 0; i < 4; i = i + 1) begin : gen_fa
            exp5_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign ripple_cout = c[4];
    assign block_prop = &p;
    assign cout = block_prop ? cin : ripple_cout;
endmodule

module exp5_full_adder (
    input  a,
    input  b,
    input  cin,
    output sum,
    output cout
);
    wire axb;
    wire ab;
    wire axb_cin;
    assign axb = a ^ b;
    assign sum = axb ^ cin;
    assign ab = a & b;
    assign axb_cin = axb & cin;
    assign cout = ab | axb_cin;
endmodule
