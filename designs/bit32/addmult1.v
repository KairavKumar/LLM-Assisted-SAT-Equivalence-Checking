// addmult1: RCA-based sum and shift-add multipliers, squaring method.
module addmult1 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [135:0] y
);
    wire [32:0] sum_ab;
    wire        cout_ab;
    wire [33:0] sum_abc;
    wire        cout_abc;

    am1_adder_rca #(33) u_add_ab (
        .a({1'b0, a}),
        .b({1'b0, b}),
        .cin(1'b0),
        .sum(sum_ab),
        .cout(cout_ab)
    );

    am1_adder_rca #(34) u_add_abc (
        .a({1'b0, sum_ab}),
        .b({2'b00, c}),
        .cin(1'b0),
        .sum(sum_abc),
        .cout(cout_abc)
    );

    wire [67:0] t2;
    wire [135:0] t4;

    am1_mult_shift_add_rca #(34, 34) u_mul2 (
        .a(sum_abc),
        .b(sum_abc),
        .product(t2)
    );

    am1_mult_shift_add_rca #(68, 68) u_mul4 (
        .a(t2),
        .b(t2),
        .product(t4)
    );

    assign y = t4;
endmodule

module am1_mult_shift_add_rca #(parameter AW = 34, parameter BW = 34) (
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

            am1_adder_rca #(PW) u_add (
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

module am1_adder_rca #(parameter W = 32) (
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
            am1_full_adder u_fa (
                .a(a[i]),
                .b(b[i]),
                .cin(c[i]),
                .sum(sum[i]),
                .cout(c[i+1])
            );
        end
    endgenerate

    assign cout = c[W];
endmodule

module am1_full_adder (
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
