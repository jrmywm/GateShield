// A Python policy oracle supplies expected decisions for accepted transactions.
// The testbench observes handshakes independently and keeps one pending result.
module tb_engine;
    parameter integer N_RULES = 8;
    localparam integer IW = (N_RULES <= 1) ? 1 : $clog2(N_RULES);
    localparam integer CW = $clog2(N_RULES + 1);
    reg clk = 0;
    always #5 clk = !clk;
    reg rst, cfg_mode, cfg_valid, req_valid, rsp_ready;
    reg [CW-1:0] cfg_index;
    reg [107:0] cfg_rule;
    reg [31:0] req_src_ip;
    reg [15:0] req_dst_port;
    reg [7:0] req_protocol;
    wire cfg_active, cfg_ready, req_ready, rsp_valid, rsp_allow, rsp_match_found;
    wire [IW-1:0] rsp_rule_index;
    gateshield_parallel #(.N_RULES(N_RULES)) dut (
        .clk(clk), .rst(rst), .cfg_mode(cfg_mode), .cfg_active(cfg_active),
        .cfg_valid(cfg_valid), .cfg_ready(cfg_ready), .cfg_index(cfg_index), .cfg_rule(cfg_rule),
        .req_valid(req_valid), .req_ready(req_ready), .req_src_ip(req_src_ip),
        .req_dst_port(req_dst_port), .req_protocol(req_protocol),
        .rsp_valid(rsp_valid), .rsp_ready(rsp_ready), .rsp_allow(rsp_allow),
        .rsp_match_found(rsp_match_found), .rsp_rule_index(rsp_rule_index)
    );
    reg [4095:0] path;
    integer fd, rc, cycle, ea, ef, ei, er, ec, ew, ev;
    integer pending, pending_allow, pending_found, pending_index;
    integer accepted, completed, canceled, writes, stalls, age;

    initial begin
        rst = 1; cfg_mode = 0; cfg_valid = 0; req_valid = 0; rsp_ready = 0;
        cfg_index = 0; cfg_rule = 0; req_src_ip = 0; req_dst_port = 0; req_protocol = 0;
        pending = 0; age = 0; accepted = 0; completed = 0; canceled = 0;
        writes = 0; stalls = 0; cycle = 0;
        if (!$value$plusargs("vectors=%s", path)) $fatal(1, "Missing vector path");
        fd = $fopen(path, "r");
        if (!fd) $fatal(1, "Cannot open engine vectors");
        while (!$feof(fd)) begin
            // Drive on falling edge and sample before the next rising edge.
            @(negedge clk);
            rc = $fscanf(fd, "%d %d %d %h %h %d %h %h %h %d %d %d %d %d %d %d %d\n",
                rst, cfg_mode, cfg_valid, cfg_index, cfg_rule, req_valid,
                req_src_ip, req_dst_port, req_protocol, rsp_ready,
                er, ec, ew, ev, ea, ef, ei);
            if (rc == 17) begin
                #1;
                if ((req_ready !== er[0]) || (cfg_active !== ec[0]) ||
                    (cfg_ready !== ew[0]) || (rsp_valid !== ev[0]))
                    $fatal(1, "Handshake mismatch cycle=%0d", cycle);
                if (rst) begin
                    if (rsp_valid || req_ready || cfg_ready || cfg_active || rsp_allow)
                        $fatal(1, "Active interface during reset cycle=%0d", cycle);
                    if (pending) canceled = canceled + 1;
                    pending = 0;
                    age = 0;
                end else begin
                    if (rsp_valid) begin
                        if (!pending) $fatal(1, "Unsolicited response cycle=%0d", cycle);
                        if ((rsp_allow !== pending_allow[0]) ||
                            (rsp_match_found !== pending_found[0]) ||
                            (rsp_rule_index !== pending_index[IW-1:0]))
                            $fatal(1, "Policy/stability mismatch cycle=%0d", cycle);
                        if (rsp_ready) begin
                            completed = completed + 1;
                            pending = 0;
                        end else stalls = stalls + 1;
                    end
                    if (req_valid && req_ready) begin
                        if (pending) $fatal(1, "Overlapping acceptance cycle=%0d", cycle);
                        pending = 1;
                        pending_allow = ea; pending_found = ef; pending_index = ei;
                        accepted = accepted + 1;
                        age = 0;
                    end else if (pending) age = age + 1;
                    // Response must be produced promptly; receiver stalls do not count as failure.
                    if (pending && !rsp_valid && age > 1)
                        $fatal(1, "Response production timeout cycle=%0d", cycle);
                    if (cfg_valid && cfg_ready) writes = writes + 1;
                end
                if (!rsp_valid && (rsp_allow || rsp_match_found || rsp_rule_index != 0))
                    $fatal(1, "Nonzero invalid response cycle=%0d", cycle);
                @(posedge clk);
                #1;
                cycle = cycle + 1;
            end else if (!$feof(fd)) $fatal(1, "Malformed engine vector");
        end
        $fclose(fd);
        if (pending || accepted != completed + canceled)
            $fatal(1, "Outstanding or lost transactions at end");
        if (completed < 100 || writes < N_RULES || stalls < 10 || canceled < 2)
            $fatal(1, "Insufficient transaction coverage");
        $display("PASS engine rules=%0d cycles=%0d accepted=%0d completed=%0d canceled=%0d writes=%0d stalled_cycles=%0d",
            N_RULES, cycle, accepted, completed, canceled, writes, stalls);
        $finish;
    end
    initial begin
        #1000000;
        $fatal(1, "Global engine test timeout");
    end
endmodule
