// 32-bit 3-input ripple-carry adder (34-bit result).
module adder3_rca32 (
    input  [31:0] a,
    input  [31:0] b,
    input  [31:0] c,
    output [33:0] sum
);
    wire [32:0] sum_ab;
    wire        cout_ab;

    adder_rca33 u_add_ab (
        .a(a),
        .b(b),
        .cin(1'b0),
        .sum(sum_ab),
        .cout(cout_ab)
    );

    wire [33:0] sum_ab_ext = {1'b0, sum_ab};
    wire [33:0] c_ext = {2'b00, c};
    wire        cout_abc;

    adder_rca34 u_add_abc (
        .a(sum_ab_ext),
        .b(c_ext),
        .cin(1'b0),
        .sum(sum),
        .cout(cout_abc)
    );
endmodule

module adder_rca33 (
    input  [31:0] a,
    input  [31:0] b,
    input         cin,
    output [32:0] sum,
    output        cout
);
    wire [33:0] c;
    assign c[0] = cin;

    genvar i;
    generate
        for (i = 0; i < 33; i = i + 1) begin : gen_fa33
            full_adder_rca u_fa (
                .a(i == 32 ? 1'b0 : a[i]),
                .b(i == 32 ? 1'b0 : b[i]),
                .cin(c[i]),
                .sum(sum[i]),
                .cout(c[i+1])
            );
        end
    endgenerate

    assign cout = c[33];
endmodule

module adder_rca34 (
    input  [33:0] a,
    input  [33:0] b,
    input         cin,
    output [33:0] sum,
    output        cout
);
    wire [34:0] c;
    assign c[0] = cin;

    genvar i;
    generate
        for (i = 0; i < 34; i = i + 1) begin : gen_fa34
            full_adder_rca u_fa (
                .a(a[i]),
                .b(b[i]),
                .cin(c[i]),
                .sum(sum[i]),
                .cout(c[i+1])
            );
        end
    endgenerate

    assign cout = c[34];
endmodule

module full_adder_rca (
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
