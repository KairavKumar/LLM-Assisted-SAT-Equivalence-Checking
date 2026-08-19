// exp4: binomial expansion using e = (a + b) with explicit modules.
module exp4 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [135:0] y
);
    localparam OUT_W = 136;

    wire [32:0] e;
    exp4_adder_csk #(33) add_e (.a({1'b0, a}), .b({1'b0, b}), .cin(1'b0), .sum(e), .cout());

    wire [65:0] e2;
    wire [98:0] e3;
    wire [131:0] e4;
    exp4_mult_csla #(33, 33) mul_e2 (.a(e), .b(e), .product(e2));
    exp4_mult_csla #(66, 33) mul_e3 (.a(e2), .b(e), .product(e3));
    exp4_mult_csla #(66, 66) mul_e4 (.a(e2), .b(e2), .product(e4));

    wire [63:0] c2;
    wire [95:0] c3;
    wire [127:0] c4;
    exp4_mult_rca #(32, 32) mul_c2 (.a(c), .b(c), .product(c2));
    exp4_mult_rca #(64, 32) mul_c3 (.a(c2), .b(c), .product(c3));
    exp4_mult_rca #(64, 64) mul_c4 (.a(c2), .b(c2), .product(c4));

    wire [129:0] e3c;
    wire [129:0] e2c2;
    wire [128:0] ec3;
    exp4_mult_cla #(99, 32) mul_e3c  (.a(e3), .b(c),  .product(e3c));
    exp4_mult_cla #(66, 64) mul_e2c2 (.a(e2), .b(c2), .product(e2c2));
    exp4_mult_cla #(33, 96) mul_ec3  (.a(e),  .b(c3), .product(ec3));

    wire [OUT_W-1:0] t4;
    exp4_adder_cla #(OUT_W) add_t4 (
        .a({4'b0, e4}),
        .b({8'b0, c4}),
        .cin(1'b0),
        .sum(t4),
        .cout()
    );

    wire [OUT_W-1:0] t3 = ({6'b0, e3c} << 2);
    wire [OUT_W-1:0] t2_sh2 = ({6'b0, e2c2} << 2);
    wire [OUT_W-1:0] t2_sh1 = ({6'b0, e2c2} << 1);
    wire [OUT_W-1:0] t2;
    exp4_adder_rca #(OUT_W) add_t2 (.a(t2_sh2), .b(t2_sh1), .cin(1'b0), .sum(t2), .cout());
    wire [OUT_W-1:0] t1 = ({7'b0, ec3} << 2);

    wire [OUT_W-1:0] y1;
    wire [OUT_W-1:0] y2;
    exp4_adder_cla #(OUT_W) add_y1 (.a(t4), .b(t3), .cin(1'b0), .sum(y1), .cout());
    exp4_adder_csk #(OUT_W) add_y2 (.a(y1), .b(t2), .cin(1'b0), .sum(y2), .cout());
    exp4_adder_rca #(OUT_W) add_y3 (.a(y2), .b(t1), .cin(1'b0), .sum(y), .cout());
endmodule

module exp4_mult_rca #(parameter AW = 32, parameter BW = 32) (
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
            exp4_adder_rca #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp4_mult_cla #(parameter AW = 32, parameter BW = 32) (
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
            exp4_adder_cla #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp4_mult_csla #(parameter AW = 32, parameter BW = 32) (
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
            exp4_adder_csk #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp4_adder_rca #(parameter W = 32) (
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
            exp4_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[W];
endmodule

module exp4_adder_cla #(parameter W = 32) (
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
        for (i = 0; i < PAD/4; i = i + 1) begin : gen_cla4
            exp4_cla4 u_cla4 (
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

module exp4_adder_csk #(parameter W = 32) (
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
            exp4_csk4 u_csk4 (
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

module exp4_csk4 (
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
            exp4_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign ripple_cout = c[4];
    assign block_prop = &p;
    assign cout = block_prop ? cin : ripple_cout;
endmodule

module exp4_cla4 (
    input  [3:0] a,
    input  [3:0] b,
    input        cin,
    output [3:0] sum,
    output       cout
);
    wire [3:0] p;
    wire [3:0] g;
    wire [4:0] c;
    assign p = a ^ b;
    assign g = a & b;
    assign c[0] = cin;
    assign c[1] = g[0] | (p[0] & c[0]);
    assign c[2] = g[1] | (p[1] & g[0]) | (p[1] & p[0] & c[0]);
    assign c[3] = g[2] | (p[2] & g[1]) | (p[2] & p[1] & g[0]) | (p[2] & p[1] & p[0] & c[0]);
    assign c[4] = g[3] | (p[3] & g[2]) | (p[3] & p[2] & g[1]) | (p[3] & p[2] & p[1] & g[0]) | (p[3] & p[2] & p[1] & p[0] & c[0]);
    assign sum = p ^ c[3:0];
    assign cout = c[4];
endmodule

module exp4_full_adder (
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
