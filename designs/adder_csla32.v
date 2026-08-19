// 32-bit carry-select adder using 4-bit blocks.
module adder_csla32 (
    input  [31:0] a,
    input  [31:0] b,
    input         cin,
    output [31:0] sum,
    output        cout
);
    wire [8:0] c_sel;
    wire [31:0] sum0;
    wire [31:0] sum1;
    wire [7:0] cout0;
    wire [7:0] cout1;

    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : gen_csla4
            rca4 u_rca0 (
                .a(a[i*4 +: 4]),
                .b(b[i*4 +: 4]),
                .cin(1'b0),
                .sum(sum0[i*4 +: 4]),
                .cout(cout0[i])
            );
            rca4 u_rca1 (
                .a(a[i*4 +: 4]),
                .b(b[i*4 +: 4]),
                .cin(1'b1),
                .sum(sum1[i*4 +: 4]),
                .cout(cout1[i])
            );
        end
    endgenerate

    assign c_sel[0] = cin;

    genvar j;
    generate
        for (j = 0; j < 8; j = j + 1) begin : gen_sel
            assign sum[j*4 +: 4] = c_sel[j] ? sum1[j*4 +: 4] : sum0[j*4 +: 4];
            assign c_sel[j+1] = c_sel[j] ? cout1[j] : cout0[j];
        end
    endgenerate

    assign cout = c_sel[8];
endmodule

module rca4 (
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
        for (i = 0; i < 4; i = i + 1) begin : gen_fa4
            full_adder_csla fa (
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

module full_adder_csla (
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
