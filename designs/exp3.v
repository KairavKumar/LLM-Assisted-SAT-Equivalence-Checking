// exp3: binomial expansion using d = (b + c) with explicit modules.
module exp3 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [135:0] y
);
    localparam OUT_W = 136;

    wire [32:0] d;
    exp3_adder_csla #(33) add_d (.a({1'b0, b}), .b({1'b0, c}), .cin(1'b0), .sum(d), .cout());

    wire [63:0] a2;
    wire [95:0] a3;
    wire [127:0] a4;
    exp3_mult_rca  #(32, 32) mul_a2 (.a(a), .b(a), .product(a2));
    exp3_mult_cla  #(64, 32) mul_a3 (.a(a2), .b(a), .product(a3));
    exp3_mult_rca  #(64, 64) mul_a4 (.a(a2), .b(a2), .product(a4));

    wire [65:0] d2;
    wire [98:0] d3;
    wire [131:0] d4;
    exp3_mult_csk  #(33, 33) mul_d2 (.a(d), .b(d), .product(d2));
    exp3_mult_csla #(66, 33) mul_d3 (.a(d2), .b(d), .product(d3));
    exp3_mult_csk  #(66, 66) mul_d4 (.a(d2), .b(d2), .product(d4));

    wire [128:0] a3d;
    wire [129:0] a2d2;
    wire [130:0] ad3;
    exp3_mult_cla  #(96, 33) mul_a3d (.a(a3), .b(d), .product(a3d));
    exp3_mult_rca  #(64, 66) mul_a2d2 (.a(a2), .b(d2), .product(a2d2));
    exp3_mult_csk  #(32, 99) mul_ad3 (.a(a), .b(d3), .product(ad3));

    wire [OUT_W-1:0] t4;
    exp3_adder_csk #(OUT_W) add_t4 (
        .a({8'b0, a4}),
        .b({4'b0, d4}),
        .cin(1'b0),
        .sum(t4),
        .cout()
    );

    wire [OUT_W-1:0] t3 = ({7'b0, a3d} << 2);
    wire [OUT_W-1:0] t2_sh2 = ({6'b0, a2d2} << 2);
    wire [OUT_W-1:0] t2_sh1 = ({6'b0, a2d2} << 1);
    wire [OUT_W-1:0] t2;
    exp3_adder_rca #(OUT_W) add_t2 (.a(t2_sh2), .b(t2_sh1), .cin(1'b0), .sum(t2), .cout());
    wire [OUT_W-1:0] t1 = ({5'b0, ad3} << 2);

    wire [OUT_W-1:0] y1;
    wire [OUT_W-1:0] y2;
    exp3_adder_csla #(OUT_W) add_y1 (.a(t4), .b(t3), .cin(1'b0), .sum(y1), .cout());
    exp3_adder_csk  #(OUT_W) add_y2 (.a(y1), .b(t2), .cin(1'b0), .sum(y2), .cout());
    exp3_adder_rca  #(OUT_W) add_y3 (.a(y2), .b(t1), .cin(1'b0), .sum(y), .cout());
endmodule

module exp3_mult_rca #(parameter AW = 32, parameter BW = 32) (
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
            exp3_adder_rca #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp3_mult_cla #(parameter AW = 32, parameter BW = 32) (
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
            exp3_adder_csk #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp3_mult_csla #(parameter AW = 32, parameter BW = 32) (
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
            exp3_adder_csla #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp3_mult_csk #(parameter AW = 32, parameter BW = 32) (
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
            exp3_adder_csk #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp3_adder_rca #(parameter W = 32) (
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
            exp3_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[W];
endmodule

module exp3_adder_csla #(parameter W = 32) (
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
    wire [PAD/4:0] c_sel;
    assign c_sel[0] = cin;
    genvar i;
    generate
        for (i = 0; i < PAD/4; i = i + 1) begin : gen_csla4
            exp3_csla4 u_csla4 (
                .a(a_pad[i*4 +: 4]),
                .b(b_pad[i*4 +: 4]),
                .cin(c_sel[i]),
                .sum(sum_pad[i*4 +: 4]),
                .cout(c_sel[i+1])
            );
        end
    endgenerate
    assign sum = sum_pad[W-1:0];
    assign cout = c_sel[PAD/4];
endmodule

module exp3_adder_csk #(parameter W = 32) (
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
            exp3_csk4 u_csk4 (
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

module exp3_csla4 (
    input  [3:0] a,
    input  [3:0] b,
    input        cin,
    output [3:0] sum,
    output       cout
);
    wire [3:0] sum0;
    wire [3:0] sum1;
    wire cout0;
    wire cout1;
    exp3_rca4 u0 (.a(a), .b(b), .cin(1'b0), .sum(sum0), .cout(cout0));
    exp3_rca4 u1 (.a(a), .b(b), .cin(1'b1), .sum(sum1), .cout(cout1));
    assign sum = cin ? sum1 : sum0;
    assign cout = cin ? cout1 : cout0;
endmodule

module exp3_rca4 (
    input  [3:0] a,
    input  [3:0] b,
    input        cin,
    output [3:0] sum,
    output       cout
);
    wire [4:0] c;
    assign c[0] = cin;
    genvar i;
    generate
        for (i = 0; i < 4; i = i + 1) begin : gen_fa
            exp3_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[4];
endmodule

module exp3_csk4 (
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
            exp3_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign ripple_cout = c[4];
    assign block_prop = &p;
    assign cout = block_prop ? cin : ripple_cout;
endmodule

module exp3_full_adder (
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
