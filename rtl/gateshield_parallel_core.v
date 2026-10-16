// Combinational policy core only. Rule table is a live input, not storage.
module gateshield_parallel_core #(
    parameter integer N_RULES = 8,
    parameter integer INDEX_W = (N_RULES <= 1) ? 1 : $clog2(N_RULES)
) (
    input wire [31:0] src_ip,
    input wire [15:0] dst_port,
    input wire [7:0] protocol,
    input wire [108*N_RULES-1:0] rules,
    output reg allow,
    output reg match_found,
    output reg [INDEX_W-1:0] rule_index
);
    wire [N_RULES-1:0] rule_hits;
    genvar g;
    generate for (g = 0; g < N_RULES; g = g + 1) begin: rule_compare
        wire [107:0] r;
        assign r = rules[g*108 +: 108];
        assign rule_hits[g] = r[106]
            && ((protocol == 8'd6) || (protocol == 8'd17))
            && ((src_ip & r[63:32]) == (r[31:0] & r[63:32]))
            && (dst_port >= r[79:64]) && (dst_port <= r[95:80])
            && (r[104] || (protocol == r[103:96]));
    end endgenerate
    integer i;
    always @* begin
        allow = 1'b0;
        match_found = 1'b0;
        rule_index = {INDEX_W{1'b0}};
        for (i = 0; i < N_RULES; i = i + 1) begin
            if (rule_hits[i] && !match_found) begin
                allow = rules[i*108 + 105];
                match_found = 1'b1;
                rule_index = i;
            end
        end
    end
endmodule
