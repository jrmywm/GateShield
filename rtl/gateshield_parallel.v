// Single-outstanding registered policy engine. See docs/specification.md.
module gateshield_parallel #(
    parameter integer N_RULES = 8,
    parameter integer INDEX_W = (N_RULES <= 1) ? 1 : $clog2(N_RULES),
    // Extra encoding(s) deliberately permit an out-of-range configuration index.
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
    reg [31:0] header_src;
    reg [15:0] header_port;
    reg [7:0] header_protocol;
    reg result_allow, result_found;
    reg [INDEX_W-1:0] result_index;
    wire core_allow, core_found;
    wire [INDEX_W-1:0] core_index;

    assign req_ready = !rst && !cfg_mode && (state == IDLE);
    assign cfg_active = !rst && (state == CONFIGURE);
    assign cfg_ready = cfg_active && cfg_mode && (cfg_index < N_RULES);
    assign rsp_valid = !rst && (state == RESPOND);
    // Clear invalid payloads as a conservative interface default.
    assign rsp_allow = rsp_valid && result_allow;
    assign rsp_match_found = rsp_valid && result_found;
    assign rsp_rule_index = rsp_valid ? result_index : {INDEX_W{1'b0}};

    gateshield_parallel_core #(.N_RULES(N_RULES), .INDEX_W(INDEX_W)) core (
        .src_ip(header_src), .dst_port(header_port), .protocol(header_protocol),
        .rules(rule_table), .allow(core_allow), .match_found(core_found),
        .rule_index(core_index)
    );

    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE;
            rule_table <= {108*N_RULES{1'b0}};
            header_src <= 0;
            header_port <= 0;
            header_protocol <= 0;
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
                        state <= EVALUATE;
                    end
                end
                EVALUATE: begin
                    result_allow <= core_allow;
                    result_found <= core_found;
                    result_index <= core_index;
                    state <= RESPOND;
                end
                RESPOND: begin
                    if (rsp_ready) state <= IDLE;
                end
                CONFIGURE: begin
                    if (!cfg_mode) state <= IDLE;
                    else if (cfg_valid && cfg_ready)
                        rule_table[cfg_index*108 +: 108] <= {1'b0, cfg_rule[106:0]};
                end
                default: begin
                    // Recover to a deny-all policy on an illegal FSM encoding.
                    state <= IDLE;
                    rule_table <= {108*N_RULES{1'b0}};
                end
            endcase
        end
    end
endmodule
