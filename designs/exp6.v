// exp6: expanded form using p=a^2+b^2+c^2 and q=ab+bc+ca with modules.
module exp6 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [135:0] y
);
    localparam OUT_W = 136;

    wire [63:0] a2;
    wire [63:0] b2;
    wire [63:0] c2;
    exp6_mult_rca #(32, 32) mul_a2 (.a(a), .b(a), .product(a2));
    exp6_mult_rca #(32, 32) mul_b2 (.a(b), .b(b), .product(b2));
    exp6_mult_rca #(32, 32) mul_c2 (.a(c), .b(c), .product(c2));

    wire [63:0] ab;
    wire [63:0] bc;
    wire [63:0] ca;
    exp6_mult_csk #(32, 32) mul_ab (.a(a), .b(b), .product(ab));
    exp6_mult_csk #(32, 32) mul_bc (.a(b), .b(c), .product(bc));
    exp6_mult_csk #(32, 32) mul_ca (.a(c), .b(a), .product(ca));

    wire [65:0] p1;
    wire [65:0] p;
    exp6_adder_cla #(66) add_p1 (.a({2'b0, a2}), .b({2'b0, b2}), .cin(1'b0), .sum(p1), .cout());
    exp6_adder_cla #(66) add_p  (.a(p1), .b({2'b0, c2}), .cin(1'b0), .sum(p), .cout());

    wire [64:0] q1;
    wire [64:0] q;
    exp6_adder_csla #(65) add_q1 (.a({1'b0, ab}), .b({1'b0, bc}), .cin(1'b0), .sum(q1), .cout());
    exp6_adder_csla #(65) add_q  (.a(q1), .b({1'b0, ca}), .cin(1'b0), .sum(q), .cout());

    wire [OUT_W-1:0] p2;
    wire [OUT_W-1:0] q2;
    wire [OUT_W-1:0] pq;
    exp6_mult_csk  #(66, 66) mul_p2 (.a(p), .b(p), .product(p2));
    exp6_mult_cla  #(65, 65) mul_q2 (.a(q), .b(q), .product(q2));
    exp6_mult_csla #(66, 65) mul_pq (.a(p), .b(q), .product(pq));

    wire [OUT_W-1:0] y1;
    wire [OUT_W-1:0] y2;
    exp6_adder_rca #(OUT_W) add_y1 (.a(p2), .b(pq << 2), .cin(1'b0), .sum(y1), .cout());
    exp6_adder_csk #(OUT_W) add_y2 (.a(y1), .b(q2 << 2), .cin(1'b0), .sum(y), .cout());
endmodule

module exp6_mult_rca #(parameter AW = 32, parameter BW = 32) (
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
            exp6_adder_rca #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp6_mult_csk #(parameter AW = 32, parameter BW = 32) (
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
            exp6_adder_csk #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp6_mult_cla #(parameter AW = 32, parameter BW = 32) (
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
            exp6_adder_cla #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp6_mult_csla #(parameter AW = 32, parameter BW = 32) (
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
            exp6_adder_csla #(PW) u_add (.a(acc[i]), .b(pp), .cin(1'b0), .sum(acc[i+1]), .cout());
        end
    endgenerate
    assign product = acc[AW];
endmodule

module exp6_adder_rca #(parameter W = 32) (
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
            exp6_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[W];
endmodule

module exp6_adder_cla #(parameter W = 32) (
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
            exp6_cla4 u_cla4 (
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

module exp6_adder_csla #(parameter W = 32) (
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
            exp6_csla4 u_csla4 (
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

module exp6_adder_csk #(parameter W = 32) (
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
            exp6_csk4 u_csk4 (
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

module exp6_csla4 (
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
    exp6_rca4 u0 (.a(a), .b(b), .cin(1'b0), .sum(sum0), .cout(cout0));
    exp6_rca4 u1 (.a(a), .b(b), .cin(1'b1), .sum(sum1), .cout(cout1));
    assign sum = cin ? sum1 : sum0;
    assign cout = cin ? cout1 : cout0;
endmodule

module exp6_rca4 (
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
            exp6_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign cout = c[4];
endmodule

module exp6_csk4 (
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
            exp6_full_adder u_fa (.a(a[i]), .b(b[i]), .cin(c[i]), .sum(sum[i]), .cout(c[i+1]));
        end
    endgenerate
    assign ripple_cout = c[4];
    assign block_prop = &p;
    assign cout = block_prop ? cin : ripple_cout;
endmodule

module exp6_cla4 (
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

module exp6_full_adder (
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
