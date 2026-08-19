// 32-bit 3-input adder using CSA + 34-bit CLA final adder.
module adder3_cla32 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [33:0] sum
);
    wire [31:0] sum_csa;
    wire [31:0] carry_csa;

    adder3_csa32_core u_csa (
        .a(a),
        .b(b),
        .c(c),
        .sum(sum_csa),
        .carry(carry_csa)
    );

    wire [33:0] x = {2'b00, sum_csa};
    wire [33:0] y = {1'b0, carry_csa, 1'b0};
    wire        cout;

    cla34 u_cla (
        .a(x),
        .b(y),
        .cin(1'b0),
        .sum(sum),
        .cout(cout)
    );
endmodule

module adder3_csa32_core (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [31:0] sum,
    output [31:0] carry
);
    genvar i;
    generate
        for (i = 0; i < 32; i = i + 1) begin : gen_csa
            assign sum[i] = a[i] ^ b[i] ^ c[i];
            assign carry[i] = (a[i] & b[i]) | (a[i] & c[i]) | (b[i] & c[i]);
        end
    endgenerate
endmodule

module cla34 (
    input  [33:0] a,
    input  [33:0] b,
    input         cin,
    output [33:0] sum,
    output        cout
);
    wire [9:0] c_block;
    assign c_block[0] = cin;

    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : gen_cla4
            cla4 u_cla4 (
                .a(a[i*4 +: 4]),
                .b(b[i*4 +: 4]),
                .cin(c_block[i]),
                .sum(sum[i*4 +: 4]),
                .cout(c_block[i+1])
            );
        end
    endgenerate

    cla2 u_cla2 (
        .a(a[33:32]),
        .b(b[33:32]),
        .cin(c_block[8]),
        .sum(sum[33:32]),
        .cout(c_block[9])
    );

    assign cout = c_block[9];
endmodule

module cla4 (
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

module cla2 (
    input  [1:0] a,
    input  [1:0] b,
    input        cin,
    output [1:0] sum,
    output       cout
);
    wire [1:0] p;
    wire [1:0] g;
    wire [2:0] c;

    assign p = a ^ b;
    assign g = a & b;

    assign c[0] = cin;
    assign c[1] = g[0] | (p[0] & c[0]);
    assign c[2] = g[1] | (p[1] & g[0]) | (p[1] & p[0] & c[0]);

    assign sum = p ^ c[1:0];
    assign cout = c[2];
endmodule
