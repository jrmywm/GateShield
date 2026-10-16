module tb_parallel;
    parameter integer N_RULES = 8;
    localparam integer IW = (N_RULES <= 1) ? 1 : $clog2(N_RULES);
    reg [31:0] src_ip;
    reg [15:0] dst_port;
    reg [7:0] protocol;
    reg [108*N_RULES-1:0] rules;
    wire allow, match_found;
    wire [IW-1:0] rule_index;
    integer fd, rc, count, ea, em, ei;
    reg [4095:0] path;
    gateshield_parallel_core #(.N_RULES(N_RULES)) dut (
        .src_ip(src_ip), .dst_port(dst_port), .protocol(protocol), .rules(rules),
        .allow(allow), .match_found(match_found), .rule_index(rule_index)
    );
    initial begin
        if (!$value$plusargs("vectors=%s", path)) $fatal(1, "Missing vector path");
        fd = $fopen(path, "r");
        if (!fd) $fatal(1, "Cannot open vectors");
        count = 0;
        while (!$feof(fd)) begin
            rc = $fscanf(fd, "%h %h %h %h %d %d %d\n", src_ip, dst_port, protocol, rules, ea, em, ei);
            if (rc == 7) begin
                #1;
                if ((allow !== ea[0]) || (match_found !== em[0]) || (rule_index !== ei[IW-1:0]))
                    $fatal(1, "Mismatch vector %0d", count);
                count = count + 1;
            end else if (!$feof(fd)) $fatal(1, "Malformed vector");
        end
        $fclose(fd);
        if (count == 0) $fatal(1, "No vectors executed");
        $display("PASS rules=%0d vectors=%0d", N_RULES, count);
        $finish;
    end
endmodule
