// addmult4: CSK-based sum and shift-add multipliers, squaring method.
module addmult4 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [135:0] y
);
    wire [33:0] sum_abc;
    wire        cout_abc;

    am4_adder_csk #(34) u_add_abc (
        .a({2'b00, a} + {2'b00, b}),
        .b({2'b00, c}),
        .cin(1'b0),
        .sum(sum_abc),
        .cout(cout_abc)
    );

    wire [67:0] t2;
    wire [135:0] t4;

    am4_mult_shift_add_csk #(34, 34) u_mul2 (
        .a(sum_abc),
        .b(sum_abc),
        .product(t2)
    );

    am4_mult_shift_add_csk #(68, 68) u_mul4 (
        .a(t2),
        .b(t2),
        .product(t4)
    );

    assign y = t4;
endmodule

module am4_mult_shift_add_csk #(parameter AW = 34, parameter BW = 34) (
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

            am4_adder_csk #(PW) u_add (
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

module am4_adder_csk #(parameter W = 32) (
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
            am4_csk4 u_csk4 (
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

module am4_csk4 (
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
            am4_full_adder u_fa (
                .a(a[i]),
                .b(b[i]),
                .cin(c[i]),
                .sum(sum[i]),
                .cout(c[i+1])
            );
        end
    endgenerate

    assign ripple_cout = c[4];
    assign block_prop = &p;
    assign cout = block_prop ? cin : ripple_cout;
endmodule

module am4_full_adder (
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
