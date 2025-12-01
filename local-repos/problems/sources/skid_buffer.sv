`timescale 1ns/1ps

module skid_buffer #(
    parameter DATA_WIDTH = 64,
    parameter BYPASS     = 0,  // 1: skid buffer with bypass, 0: simple 2-entry FIFO (no bypass)
    parameter DEPTH = 2    // only for no bypass
)(
    input                    clk,
    input                    rst_n,         // active-low async reset
    input  [DATA_WIDTH-1:0]  s_data,
    input                    s_valid,
    output                   s_ready,
    output [DATA_WIDTH-1:0]  m_data,
    output                   m_valid,
    input                    m_ready
);

    generate if (BYPASS) begin : g_bypass
        // Two-entry skid buffer using explicit front/back registers
        reg                      skid_valid;
        reg [DATA_WIDTH-1:0]     skid_data;

        wire empty  = ~skid_valid;
        wire bypass = empty;   

        assign m_data  = skid_valid ? skid_data : s_data;
        assign m_valid = skid_valid ? 1'b1      : s_valid;

        //ready flow:
        //when empty = 1, skid buffer can receive data, s_ready = 1
        //if skid_buff is full, s_ready only m_ready
        assign s_ready = empty || m_ready;

        reg                      skid_valid_next;
        reg [DATA_WIDTH-1:0]     skid_data_next;

        // Next-state combinational logic
        always @(*) begin
            skid_valid_next = skid_valid;
            skid_data_next  = skid_data;

            if (empty) begin
                // No skid data currently stored
                if (s_valid && !m_ready) begin
                    // Upstream provides data but downstream stalls:
                    // Capture this beat in the skid register
                    skid_valid_next = 1'b1;
                    skid_data_next  = s_data;
                end
                // Other cases:
                // - s_valid && m_ready: full bypass, no storage
                // - s_valid=0: nothing to do
            end else begin
                // Skid register holds valid data
                if (m_ready) begin
                    // Downstream consumes current output
                    if (s_valid) begin
                        // Capture the new upstream data immediately
                        skid_valid_next = 1'b1;
                        skid_data_next  = s_data;
                    end else begin
                        // No new data: skid becomes empty
                        skid_valid_next = 1'b0;
                    end
                end
                // If m_ready=0: downstream stall, hold skid as-is
            end
        end

        // Sequential state update
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) begin
                skid_valid <= 1'b0;
                skid_data  <= {DATA_WIDTH{1'b0}};
            end else begin
                skid_valid <= skid_valid_next;
                skid_data  <= skid_data_next;
            end
        end 

end else begin : g_fifo
    // ============================================================
    // BYPASS = 0 : 2-entry FIFO (always 1-cycle latency)
    // ============================================================
    
        // Simple circular FIFO with (DEPTH) entries
        localparam CNT_W = $clog2(DEPTH + 1);
        localparam PTR_W = $clog2(DEPTH);

        reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];
        reg [PTR_W-1:0]      rd_ptr;
        reg [PTR_W-1:0]      wr_ptr;
        reg [CNT_W-1:0]      count;

        wire full  = (count == DEPTH[CNT_W-1:0]);
        wire empty = (count == {CNT_W{1'b0}});

        // Handshake
        assign s_ready = !full;
        assign m_valid = !empty;
        assign m_data  = mem[rd_ptr];

        wire do_enqueue = s_valid && s_ready;
        wire do_dequeue = m_valid && m_ready;

        // Combinational next-state for pointers and count
        reg [PTR_W-1:0] rd_ptr_next;
        reg [PTR_W-1:0] wr_ptr_next;
        reg [CNT_W-1:0] count_next;

        always @(*) begin
            rd_ptr_next = rd_ptr;
            wr_ptr_next = wr_ptr;
            count_next  = count;

            case ({do_dequeue, do_enqueue})
                2'b00: begin
                    // Hold pointers and count
                end

                2'b01: begin
                    // Enqueue only
                    count_next  = count + 1'b1;
                    // Write pointer will be updated in sequential block
                    // Data write happens in sequential block as well
                    wr_ptr_next = (wr_ptr == DEPTH-1) ? {PTR_W{1'b0}} : wr_ptr + 1'b1;
                end

                2'b10: begin
                    // Dequeue only
                    count_next  = count - 1'b1;
                    rd_ptr_next = (rd_ptr == DEPTH-1) ? {PTR_W{1'b0}} : rd_ptr + 1'b1;
                end

                2'b11: begin
                    // Enqueue and dequeue in the same cycle: count unchanged
                    // Both pointers move
                    rd_ptr_next = (rd_ptr == DEPTH-1) ? {PTR_W{1'b0}} : rd_ptr + 1'b1;
                    wr_ptr_next = (wr_ptr == DEPTH-1) ? {PTR_W{1'b0}} : wr_ptr + 1'b1;
                end
            endcase
        end

        // Sequential block: update pointers, count, and memory
        integer i;
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) begin
                rd_ptr <= {PTR_W{1'b0}};
                wr_ptr <= {PTR_W{1'b0}};
                count  <= {CNT_W{1'b0}};
                // Optional init for mem
                for (i = 0; i < DEPTH; i = i + 1) begin
                    mem[i] <= {DATA_WIDTH{1'b0}};
                end
            end else begin
                // Write data on enqueue
                if (do_enqueue) begin
                    mem[wr_ptr] <= s_data;
                end

                rd_ptr <= rd_ptr_next;
                wr_ptr <= wr_ptr_next;
                count  <= count_next;
            end
        end

        // Optional assertion examples
        // always @(posedge clk) begin
        //     if (do_dequeue) assert(!empty);
        //     if (do_enqueue) assert(!full);
        // end
    end endgenerate
endmodule