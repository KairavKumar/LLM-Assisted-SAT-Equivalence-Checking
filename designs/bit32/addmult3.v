// addmult3: CSLA-based sum and shift-add multipliers, sequential multiply.
module addmult3 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [135:0] y
);
    wire [33:0] sum_abc;
    wire        cout_abc;

    am3_adder_csla #(34) u_add_abc (
        .a({2'b00, a} + {2'b00, b}),
        .b({2'b00, c}),
        .cin(1'b0),
        .sum(sum_abc),
        .cout(cout_abc)
    );

    wire [67:0] t2;
    wire [101:0] t3;
    wire [135:0] t4;

    am3_mult_shift_add_csla #(34, 34) u_mul2 (
        .a(sum_abc),
        .b(sum_abc),
        .product(t2)
    );

    am3_mult_shift_add_csla #(68, 34) u_mul3 (
        .a(t2),
        .b(sum_abc),
        .product(t3)
    );

    am3_mult_shift_add_csla #(102, 34) u_mul4 (
        .a(t3),
        .b(sum_abc),
        .product(t4)
    );

    assign y = t4;
endmodule

module am3_mult_shift_add_csla #(parameter AW = 34, parameter BW = 34) (
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

            am3_adder_csla #(PW) u_add (
                .a(acc[i]),
                .b(pp),
                .cin(1'b0),
                .sum(acc[i+1]),
                .cout()
            );
        end
    endgenerate

    assign product = acc[AW];
endmodule

module am3_adder_csla #(parameter W = 32) (
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
            am3_csla4 u_csla4 (
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

module am3_csla4 (
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

    am3_rca4 u0 (
        .a(a),
        .b(b),
        .cin(1'b0),
        .sum(sum0),
        .cout(cout0)
    );

    am3_rca4 u1 (
        .a(a),
        .b(b),
        .cin(1'b1),
        .sum(sum1),
        .cout(cout1)
    );

    assign sum = cin ? sum1 : sum0;
    assign cout = cin ? cout1 : cout0;
endmodule

module am3_rca4 (
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
            am3_full_adder u_fa (
                .a(a[i]),
                .b(b[i]),
                .cin(c[i]),
                .sum(sum[i]),
                .cout(c[i+1])
            );
        end
    endgenerate

    assign cout = c[4];
endmodule

module am3_full_adder (
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
