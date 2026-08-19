// 32-bit 3-input carry-save adder (sum + carry).
module adder3_csa32 (
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
