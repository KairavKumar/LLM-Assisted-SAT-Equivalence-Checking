// exp1: full multinomial expansion with varied adders and multipliers.
module exp1 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [135:0] y
);
    localparam OUT_W = 136;

    wire [63:0] a2;
    wire [63:0] b2;
    wire [63:0] c2;
    exp1_mult_rca #(32, 32) mul_a2 (.a(a), .b(a), .product(a2));
    exp1_mult_rca #(32, 32) mul_b2 (.a(b), .b(b), .product(b2));
    exp1_mult_rca #(32, 32) mul_c2 (.a(c), .b(c), .product(c2));

    wire [95:0] a3;
    wire [95:0] b3;
    wire [95:0] c3;
    exp1_mult_cla #(64, 32) mul_a3 (.a(a2), .b(a), .product(a3));
    exp1_mult_cla #(64, 32) mul_b3 (.a(b2), .b(b), .product(b3));
    exp1_mult_cla #(64, 32) mul_c3 (.a(c2), .b(c), .product(c3));

    wire [127:0] a4;
    wire [127:0] b4;
    wire [127:0] c4;
    exp1_mult_csla #(64, 64) mul_a4 (.a(a2), .b(a2), .product(a4));
    exp1_mult_csla #(64, 64) mul_b4 (.a(b2), .b(b2), .product(b4));
    exp1_mult_csla #(64, 64) mul_c4 (.a(c2), .b(c2), .product(c4));

    wire [63:0] ab;
    wire [63:0] ac;
    wire [63:0] bc;
    exp1_mult_csk #(32, 32) mul_ab (.a(a), .b(b), .product(ab));
    exp1_mult_csk #(32, 32) mul_ac (.a(a), .b(c), .product(ac));
    exp1_mult_csk #(32, 32) mul_bc (.a(b), .b(c), .product(bc));

    wire [127:0] a3b;
    wire [127:0] a3c;
    wire [127:0] b3a;
    wire [127:0] b3c;
    wire [127:0] c3a;
    wire [127:0] c3b;
    exp1_mult_cla  #(96, 32) mul_a3b (.a(a3), .b(b), .product(a3b));
    exp1_mult_cla  #(96, 32) mul_a3c (.a(a3), .b(c), .product(a3c));
    exp1_mult_rca  #(96, 32) mul_b3a (.a(b3), .b(a), .product(b3a));
    exp1_mult_rca  #(96, 32) mul_b3c (.a(b3), .b(c), .product(b3c));
    exp1_mult_csla #(96, 32) mul_c3a (.a(c3), .b(a), .product(c3a));
    exp1_mult_csla #(96, 32) mul_c3b (.a(c3), .b(b), .product(c3b));

    wire [127:0] a2b2;
    wire [127:0] a2c2;
    wire [127:0] b2c2;
    exp1_mult_csk #(64, 64) mul_a2b2 (.a(a2), .b(b2), .product(a2b2));
    exp1_mult_csk #(64, 64) mul_a2c2 (.a(a2), .b(c2), .product(a2c2));
    exp1_mult_csk #(64, 64) mul_b2c2 (.a(b2), .b(c2), .product(b2c2));

    wire [127:0] a2bc;
    wire [127:0] b2ac;
    wire [127:0] c2ab;
    exp1_mult_rca  #(64, 64) mul_a2bc (.a(a2), .b(bc), .product(a2bc));
    exp1_mult_cla  #(64, 64) mul_b2ac (.a(b2), .b(ac), .product(b2ac));
    exp1_mult_csla #(64, 64) mul_c2ab (.a(c2), .b(ab), .product(c2ab));

    wire [OUT_W-1:0] a4e = {8'b0, a4};
    wire [OUT_W-1:0] b4e = {8'b0, b4};
    wire [OUT_W-1:0] c4e = {8'b0, c4};

    wire [OUT_W-1:0] t4_ab;
    wire [OUT_W-1:0] t4;
    exp1_adder_cla  #(OUT_W) add_t4_ab (.a(a4e), .b(b4e), .cin(1'b0), .sum(t4_ab), .cout());
    exp1_adder_rca  #(OUT_W) add_t4    (.a(t4_ab), .b(c4e), .cin(1'b0), .sum(t4), .cout());

    wire [OUT_W-1:0] a3be = {8'b0, a3b};
    wire [OUT_W-1:0] a3ce = {8'b0, a3c};
    wire [OUT_W-1:0] b3ae = {8'b0, b3a};
    wire [OUT_W-1:0] b3ce = {8'b0, b3c};
    wire [OUT_W-1:0] c3ae = {8'b0, c3a};
    wire [OUT_W-1:0] c3be = {8'b0, c3b};

    wire [OUT_W-1:0] t3_1;
    wire [OUT_W-1:0] t3_2;
    wire [OUT_W-1:0] t3_3;
    wire [OUT_W-1:0] t3_4;
    wire [OUT_W-1:0] t3_raw;
    exp1_adder_csla #(OUT_W) add_t3_1 (.a(a3be), .b(a3ce), .cin(1'b0), .sum(t3_1), .cout());
    exp1_adder_csk  #(OUT_W) add_t3_2 (.a(t3_1), .b(b3ae), .cin(1'b0), .sum(t3_2), .cout());
    exp1_adder_rca  #(OUT_W) add_t3_3 (.a(t3_2), .b(b3ce), .cin(1'b0), .sum(t3_3), .cout());
    exp1_adder_cla  #(OUT_W) add_t3_4 (.a(t3_3), .b(c3ae), .cin(1'b0), .sum(t3_4), .cout());
    exp1_adder_csla #(OUT_W) add_t3_r (.a(t3_4), .b(c3be), .cin(1'b0), .sum(t3_raw), .cout());

    wire [OUT_W-1:0] t3 = t3_raw << 2;

    wire [OUT_W-1:0] a2b2e = {8'b0, a2b2};
    wire [OUT_W-1:0] a2c2e = {8'b0, a2c2};
    wire [OUT_W-1:0] b2c2e = {8'b0, b2c2};

    wire [OUT_W-1:0] t22_1;
    wire [OUT_W-1:0] t22_raw;
    exp1_adder_cla #(OUT_W) add_t22_1 (.a(a2b2e), .b(a2c2e), .cin(1'b0), .sum(t22_1), .cout());
    exp1_adder_rca #(OUT_W) add_t22_r (.a(t22_1), .b(b2c2e), .cin(1'b0), .sum(t22_raw), .cout());

    wire [OUT_W-1:0] t22_sh2 = t22_raw << 2;
    wire [OUT_W-1:0] t22_sh1 = t22_raw << 1;
    wire [OUT_W-1:0] t22;
    exp1_adder_rca #(OUT_W) add_t22 (.a(t22_sh2), .b(t22_sh1), .cin(1'b0), .sum(t22), .cout());

    wire [OUT_W-1:0] a2bce = {8'b0, a2bc};
    wire [OUT_W-1:0] b2ace = {8'b0, b2ac};
    wire [OUT_W-1:0] c2abe = {8'b0, c2ab};

    wire [OUT_W-1:0] t211_1;
    wire [OUT_W-1:0] t211_raw;
    exp1_adder_rca #(OUT_W) add_t211_1 (.a(a2bce), .b(b2ace), .cin(1'b0), .sum(t211_1), .cout());
    exp1_adder_csk #(OUT_W) add_t211_r (.a(t211_1), .b(c2abe), .cin(1'b0), .sum(t211_raw), .cout());

    wire [OUT_W-1:0] t211_sh3 = t211_raw << 3;
    wire [OUT_W-1:0] t211_sh2 = t211_raw << 2;
    wire [OUT_W-1:0] t211;
    exp1_adder_cla #(OUT_W) add_t211 (.a(t211_sh3), .b(t211_sh2), .cin(1'b0), .sum(t211), .cout());

    wire [OUT_W-1:0] y1;
    wire [OUT_W-1:0] y2;
    exp1_adder_csla #(OUT_W) add_y1 (.a(t4), .b(t3), .cin(1'b0), .sum(y1), .cout());
    exp1_adder_cla  #(OUT_W) add_y2 (.a(y1), .b(t22), .cin(1'b0), .sum(y2), .cout());
    exp1_adder_rca  #(OUT_W) add_y3 (.a(y2), .b(t211), .cin(1'b0), .sum(y), .cout());
endmodule

module exp1_mult_rca #(parameter AW = 32, parameter BW = 32) (
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
            exp1_adder_rca #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp1_mult_cla #(parameter AW = 32, parameter BW = 32) (
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
            exp1_adder_cla #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp1_mult_csla #(parameter AW = 32, parameter BW = 32) (
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
            exp1_adder_csla #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp1_mult_csk #(parameter AW = 32, parameter BW = 32) (
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
            exp1_adder_csk #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp1_adder_rca #(parameter W = 32) (
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
            exp1_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[W];
endmodule

module exp1_adder_cla #(parameter W = 32) (
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
            exp1_cla4 u_cla4 (
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

module exp1_adder_csla #(parameter W = 32) (
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
            exp1_csla4 u_csla4 (
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

module exp1_adder_csk #(parameter W = 32) (
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
            exp1_csk4 u_csk4 (
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

module exp1_csla4 (
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

    exp1_rca4 u0 (.a(a), .b(b), .cin(1'b0), .sum(sum0), .cout(cout0));
    exp1_rca4 u1 (.a(a), .b(b), .cin(1'b1), .sum(sum1), .cout(cout1));

    assign sum = cin ? sum1 : sum0;
    assign cout = cin ? cout1 : cout0;
endmodule

module exp1_rca4 (
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
            exp1_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate

    assign cout = c[4];
endmodule

module exp1_csk4 (
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
            exp1_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate

    assign ripple_cout = c[4];
    assign block_prop = &p;
    assign cout = block_prop ? cin : ripple_cout;
endmodule

module exp1_cla4 (
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

module exp1_full_adder (
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
