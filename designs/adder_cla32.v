// 32-bit carry-lookahead adder using 4-bit CLA blocks.
module adder_cla32 (
    input  [31:0] a,
    input  [31:0] b,
    input         cin,
    output [31:0] sum,
    output        cout
);
    wire [8:0] c_block;
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

    assign cout = c_block[8];
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
