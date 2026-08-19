// 32-bit radix-2 Booth multiplier (2-input).
module mult_booth32 (
    input  [31:0] a,
    input  [31:0] b,
    output [63:0] product
);
    wire signed [63:0] acc [0:32];
    wire signed [63:0] b_ext;
    assign acc[0] = 64'sd0;
    assign b_ext = {{32{b[31]}}, b};

    genvar i;
    generate
        for (i = 0; i < 32; i = i + 1) begin : gen_booth
            wire prev;
            wire [1:0] recode;
            wire signed [63:0] pp;

            assign prev = (i == 0) ? 1'b0 : a[i-1];
            assign recode = {a[i], prev};

            assign pp = (recode == 2'b01) ? (b_ext <<< i) :
                        (recode == 2'b10) ? -(b_ext <<< i) :
                        64'sd0;

            adder_rca64_booth u_add (
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

module adder_rca64_booth (
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
            full_adder_booth u_fa (
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

module full_adder_booth (
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
