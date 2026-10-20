// One comparator group scans rules in priority order, one rule per clock.
// Storage, configuration, and response semantics match gateshield_parallel.
module gateshield_sequential #(
    parameter integer N_RULES = 8,
    parameter integer INDEX_W = (N_RULES <= 1) ? 1 : $clog2(N_RULES),
    parameter integer CFG_INDEX_W = $clog2(N_RULES + 1)
) (
    input wire clk,
    input wire rst,
    input wire cfg_mode,
    output wire cfg_active,
    input wire cfg_valid,
    output wire cfg_ready,
    input wire [CFG_INDEX_W-1:0] cfg_index,
    input wire [107:0] cfg_rule,
    input wire req_valid,
    output wire req_ready,
    input wire [31:0] req_src_ip,
    input wire [15:0] req_dst_port,
    input wire [7:0] req_protocol,
    output wire rsp_valid,
    input wire rsp_ready,
    output wire rsp_allow,
    output wire rsp_match_found,
    output wire [INDEX_W-1:0] rsp_rule_index
);
    localparam [1:0] IDLE = 2'd0, EVALUATE = 2'd1,
                     RESPOND = 2'd2, CONFIGURE = 2'd3;
    reg [1:0] state;
    reg [108*N_RULES-1:0] rule_table;
    integer k;
    reg [31:0] header_src;
    reg [15:0] header_port;
    reg [7:0] header_protocol;
    reg [INDEX_W-1:0] scan_index;
    reg result_allow, result_found;
    reg [INDEX_W-1:0] result_index;
    wire [107:0] selected_rule;
    wire rule_hit;

    assign req_ready = !rst && !cfg_mode && (state == IDLE);
    assign cfg_active = !rst && (state == CONFIGURE);
    assign cfg_ready = cfg_active && cfg_mode && (cfg_index < N_RULES);
    assign rsp_valid = !rst && (state == RESPOND);
    assign rsp_allow = rsp_valid && result_allow;
    assign rsp_match_found = rsp_valid && result_found;
    assign rsp_rule_index = rsp_valid ? result_index : {INDEX_W{1'b0}};

    // Explicit rule select. Written as rule_table[scan_index*108 +: 108] this
    // costs ~5.7x more generic cells (barrel shifter); see docs/findings.md.
    reg [107:0] selected_rule_r;
    integer j;
    always @* begin
        selected_rule_r = 108'd0;
        for (j = 0; j < N_RULES; j = j + 1)
            if (scan_index == j) selected_rule_r = rule_table[j*108 +: 108];
    end
    assign selected_rule = selected_rule_r;
    assign rule_hit = selected_rule[106]
        && ((header_protocol == 8'd6) || (header_protocol == 8'd17))
        && ((header_src & selected_rule[63:32]) ==
            (selected_rule[31:0] & selected_rule[63:32]))
        && (header_port >= selected_rule[79:64])
        && (header_port <= selected_rule[95:80])
        && (selected_rule[104] || (header_protocol == selected_rule[103:96]));

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            rule_table <= {108*N_RULES{1'b0}};
            header_src <= 0;
            header_port <= 0;
            header_protocol <= 0;
            scan_index <= 0;
            result_allow <= 0;
            result_found <= 0;
            result_index <= 0;
        end else begin
            case (state)
                IDLE: begin
                    if (cfg_mode) state <= CONFIGURE;
                    else if (req_valid && req_ready) begin
                        header_src <= req_src_ip;
                        header_port <= req_dst_port;
                        header_protocol <= req_protocol;
                        scan_index <= 0;
                        state <= EVALUATE;
                    end
                end
                EVALUATE: begin
                    if (rule_hit) begin
                        result_allow <= selected_rule[105];
                        result_found <= 1;
                        result_index <= scan_index;
                        state <= RESPOND;
                    end else if (scan_index == N_RULES-1) begin
                        result_allow <= 0;
                        result_found <= 0;
                        result_index <= 0;
                        state <= RESPOND;
                    end else scan_index <= scan_index + 1'b1;
                end
                RESPOND: begin
                    if (rsp_ready) state <= IDLE;
                end
                CONFIGURE: begin
                    if (!cfg_mode) state <= IDLE;
                    else if (cfg_valid && cfg_ready) begin
                        // Constant slice per rule, gated by an index compare. A
                        // variable-offset part-select here synthesizes to a
                        // barrel shifter over the whole table; see docs/findings.md.
                        for (k = 0; k < N_RULES; k = k + 1)
                            if (cfg_index == k)
                                rule_table[k*108 +: 108] <= {1'b0, cfg_rule[106:0]};
                    end
                end
                default: begin
                    state <= IDLE;
                    rule_table <= {108*N_RULES{1'b0}};
                end
            endcase
        end
    end
endmodule
