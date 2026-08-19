// 32-bit 3-input multiplier: product = a * b * c (96-bit output).
module mult3_array32 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [95:0] product
);
    wire [63:0] ab;

    mult_array32_core u_mul_ab (
        .a(a),
        .b(b),
        .product(ab)
    );

    wire [95:0] acc [0:32];
    assign acc[0] = 96'b0;

    genvar i;
    generate
        for (i = 0; i < 32; i = i + 1) begin : gen_mul_c
            wire [95:0] pp;
            assign pp = c[i] ? ({32'b0, ab} << i) : 96'b0;

            adder_rca96 u_add (
                .a(acc[i]),
                .b(pp),
                .cin(1'b0),
                .sum(acc[i+1]),
                .cout()
            );
        end
    endgenerate

    assign product = acc[32];
endmodule

module mult_array32_core (
    input  [31:0] a,
    input  [31:0] b,
    output [63:0] product
);
    wire [63:0] acc [0:32];
    assign acc[0] = 64'b0;

    genvar i;
    generate
        for (i = 0; i < 32; i = i + 1) begin : gen_acc
            wire [63:0] pp;
            assign pp = a[i] ? ({32'b0, b} << i) : 64'b0;

            adder_rca64_m3 u_add (
                .a(acc[i]),
                .b(pp),
                .cin(1'b0),
                .sum(acc[i+1]),
                .cout()
            );
        end
    endgenerate

    assign product = acc[32];
endmodule

module adder_rca96 (
    input  [95:0] a,
    input  [95:0] b,
    input         cin,
    output [95:0] sum,
    output        cout
);
    wire [96:0] c;
    assign c[0] = cin;

    genvar i;
    generate
        for (i = 0; i < 96; i = i + 1) begin : gen_fa96
            full_adder_m3 u_fa (
                .a(a[i]),
                .b(b[i]),
                .cin(c[i]),
                .sum(sum[i]),
                .cout(c[i+1])
            );
        end
    endgenerate

    assign cout = c[96];
endmodule

module adder_rca64_m3 (
    input  [63:0] a,
    input  [63:0] b,
    input         cin,
    output [63:0] sum,
    output        cout
);
    wire [64:0] c;
    assign c[0] = cin;

    genvar i;
    generate
        for (i = 0; i < 64; i = i + 1) begin : gen_fa64
            full_adder_m3 u_fa (
                .a(a[i]),
                .b(b[i]),
                .cin(c[i]),
                .sum(sum[i]),
                .cout(c[i+1])
            );
        end
    endgenerate

    assign cout = c[64];
endmodule

module full_adder_m3 (
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
