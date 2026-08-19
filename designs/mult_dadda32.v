// 32-bit Dadda tree multiplier (2-input) using CSA reduction.
module mult_dadda32 (
    input  [31:0] a,
    input  [31:0] b,
    output [63:0] product
);
    wire [63:0] pp [0:31];

    genvar i;
    generate
        for (i = 0; i < 32; i = i + 1) begin : gen_pp
            assign pp[i] = a[i] ? ({32'b0, b} << i) : 64'b0;
        end
    endgenerate

    // Stage 1: 32 -> 22
    wire [63:0] s1 [0:9];
    wire [63:0] c1 [0:9];
    generate
        for (i = 0; i < 10; i = i + 1) begin : gen_s1
            csa64_dadda u_csa1 (
                .a(pp[i*3]),
                .b(pp[i*3 + 1]),
                .c(pp[i*3 + 2]),
                .sum(s1[i]),
                .carry(c1[i])
            );
        end
    endgenerate

    wire [63:0] op2 [0:21];
    generate
        for (i = 0; i < 10; i = i + 1) begin : gen_op2
            assign op2[i] = s1[i];
            assign op2[i+10] = {c1[i][62:0], 1'b0};
        end
    endgenerate
    assign op2[20] = pp[30];
    assign op2[21] = pp[31];

    // Stage 2: 22 -> 15
    wire [63:0] s2 [0:6];
    wire [63:0] c2 [0:6];
    generate
        for (i = 0; i < 7; i = i + 1) begin : gen_s2
            csa64_dadda u_csa2 (
                .a(op2[i*3]),
                .b(op2[i*3 + 1]),
                .c(op2[i*3 + 2]),
                .sum(s2[i]),
                .carry(c2[i])
            );
        end
    endgenerate

    wire [63:0] op3 [0:14];
    generate
        for (i = 0; i < 7; i = i + 1) begin : gen_op3
            assign op3[i] = s2[i];
            assign op3[i+7] = {c2[i][62:0], 1'b0};
        end
    endgenerate
    assign op3[14] = op2[21];

    // Stage 3: 15 -> 10
    wire [63:0] s3 [0:4];
    wire [63:0] c3 [0:4];
    generate
        for (i = 0; i < 5; i = i + 1) begin : gen_s3
            csa64_dadda u_csa3 (
                .a(op3[i*3]),
                .b(op3[i*3 + 1]),
                .c(op3[i*3 + 2]),
                .sum(s3[i]),
                .carry(c3[i])
            );
        end
    endgenerate

    wire [63:0] op4 [0:9];
    generate
        for (i = 0; i < 5; i = i + 1) begin : gen_op4
            assign op4[i] = s3[i];
            assign op4[i+5] = {c3[i][62:0], 1'b0};
        end
    endgenerate

    // Stage 4: 10 -> 7
    wire [63:0] s4 [0:2];
    wire [63:0] c4 [0:2];
    generate
        for (i = 0; i < 3; i = i + 1) begin : gen_s4
            csa64_dadda u_csa4 (
                .a(op4[i*3]),
                .b(op4[i*3 + 1]),
                .c(op4[i*3 + 2]),
                .sum(s4[i]),
                .carry(c4[i])
            );
        end
    endgenerate

    wire [63:0] op5 [0:6];
    generate
        for (i = 0; i < 3; i = i + 1) begin : gen_op5
            assign op5[i] = s4[i];
            assign op5[i+3] = {c4[i][62:0], 1'b0};
        end
    endgenerate
    assign op5[6] = op4[9];

    // Stage 5: 7 -> 5
    wire [63:0] s5 [0:1];
    wire [63:0] c5 [0:1];
    generate
        for (i = 0; i < 2; i = i + 1) begin : gen_s5
            csa64_dadda u_csa5 (
                .a(op5[i*3]),
                .b(op5[i*3 + 1]),
                .c(op5[i*3 + 2]),
                .sum(s5[i]),
                .carry(c5[i])
            );
        end
    endgenerate

    wire [63:0] op6 [0:4];
    generate
        for (i = 0; i < 2; i = i + 1) begin : gen_op6
            assign op6[i] = s5[i];
            assign op6[i+2] = {c5[i][62:0], 1'b0};
        end
    endgenerate
    assign op6[4] = op5[6];

    // Stage 6: 5 -> 4
    wire [63:0] s6;
    wire [63:0] c6;
    csa64_dadda u_csa6 (
        .a(op6[0]),
        .b(op6[1]),
        .c(op6[2]),
        .sum(s6),
        .carry(c6)
    );

    wire [63:0] op7 [0:3];
    assign op7[0] = s6;
    assign op7[1] = {c6[62:0], 1'b0};
    assign op7[2] = op6[3];
    assign op7[3] = op6[4];

    // Stage 7: 4 -> 3
    wire [63:0] s7;
    wire [63:0] c7;
    csa64_dadda u_csa7 (
        .a(op7[0]),
        .b(op7[1]),
        .c(op7[2]),
        .sum(s7),
        .carry(c7)
    );

    wire [63:0] op8 [0:2];
    assign op8[0] = s7;
    assign op8[1] = {c7[62:0], 1'b0};
    assign op8[2] = op7[3];

    // Stage 8: 3 -> 2
    wire [63:0] s8;
    wire [63:0] c8;
    csa64_dadda u_csa8 (
        .a(op8[0]),
        .b(op8[1]),
        .c(op8[2]),
        .sum(s8),
        .carry(c8)
    );

    adder_rca64_dadda u_add (
        .a(s8),
        .b({c8[62:0], 1'b0}),
        .cin(1'b0),
        .sum(product),
        .cout()
    );
endmodule

module csa64_dadda (
    input  [63:0] a,
    input  [63:0] b,
    input  [63:0] c,
    output [63:0] sum,
    output [63:0] carry
);
    assign sum = a ^ b ^ c;
    assign carry = (a & b) | (a & c) | (b & c);
endmodule

module adder_rca64_dadda (
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
            full_adder_dadda u_fa (
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

module full_adder_dadda (
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
