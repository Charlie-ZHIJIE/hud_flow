`timescale 1ns/1ps
`default_nettype none

module rx_mac_stream #(
    parameter int DATA_WIDTH   = 32,
    localparam int DATA_NBYTES = DATA_WIDTH / 8
) (
    input  wire                     i_clk,
    input  wire                     i_reset,
    // ---------------------------------------------------------------------
    // Input Stream from PHY / PCS
    // Assumptions:
    //   * Data contains payload only (no preamble, no SFD, no FCS)
    //   * FCS is provided separately via i_rx_fcs when TLAST is asserted
    //   * s_axis_tvalid=1 indicates that a frame is being received
    // ---------------------------------------------------------------------
    input  wire [DATA_WIDTH-1:0]    s_axis_tdata,
    input  wire [DATA_NBYTES-1:0]   s_axis_tkeep,
    input  wire                     s_axis_tvalid,
    input  wire                     s_axis_tlast,
    // Received FCS sideband
    // Must be valid when s_axis_tlast==1
    input  wire [31:0]              i_rx_fcs,
    input  wire                     i_rx_fcs_valid,
    // ---------------------------------------------------------------------
    // Output Stream (AXIS-like)
    // tuser is only meaningful when tlast=1:
    //    1'b1 = CRC OK
    //    1'b0 = CRC error
    // ---------------------------------------------------------------------
    output logic [DATA_WIDTH-1:0]   m_axis_tdata,
    output logic [DATA_NBYTES-1:0]  m_axis_tkeep,
    output logic                    m_axis_tvalid,
    output logic                    m_axis_tlast,
    output logic                    m_axis_tuser
);

    // =====================================================================
    // Internal State Machine
    // =====================================================================
    typedef enum logic [1:0] {
        S_IDLE,     // Waiting for start of frame
        S_DATA      // Receiving frame payload
    } rx_state_t;

    rx_state_t state, state_next;

    // CRC result computed for the current frame
    logic [31:0] crc_calc;

    // CRC check result latched on TLAST
    logic crc_ok_reg, crc_ok_next;

    // Reset CRC when idle and no valid data
    // CRC should NOT be reset when first beat arrives (so it gets computed)
    wire crc_reset = (state == S_IDLE) && !s_axis_tvalid;

    // =====================================================================
    // State Update
    // =====================================================================
    always_ff @(posedge i_clk) begin
        if (i_reset) begin
            state      <= S_IDLE;
            crc_ok_reg <= 1'b0;
        end else begin
            state      <= state_next;
            crc_ok_reg <= crc_ok_next;
        end
    end

    // =====================================================================
    // State Machine & Output Logic
    // =====================================================================
    always_comb begin
        // Default assignments
        state_next    = state;
        crc_ok_next   = crc_ok_reg;
        m_axis_tdata  = s_axis_tdata;
        m_axis_tkeep  = s_axis_tkeep;
        m_axis_tvalid = s_axis_tvalid;
        m_axis_tlast  = s_axis_tlast;
        m_axis_tuser  = 1'b0;

        unique case (state)
            // -------------------------------------------------------------
            // IDLE
            // When valid data arrives, immediately pass it through and
            // transition to DATA state
            // -------------------------------------------------------------
            S_IDLE: begin
                if (s_axis_tvalid) begin
                    // Start receiving a new frame - pass through first beat
                    m_axis_tdata  = s_axis_tdata;
                    m_axis_tkeep  = s_axis_tkeep;
                    m_axis_tvalid = 1'b1;
                    m_axis_tlast  = s_axis_tlast;
                    state_next = S_DATA;
                    
                    // Handle single-beat frame (tlast on first beat)
                    if (s_axis_tlast) begin
                        if (i_rx_fcs_valid) begin
                            crc_ok_next = (crc_calc == i_rx_fcs);
                        end else begin
                            crc_ok_next = 1'b0;
                        end
                        m_axis_tuser = crc_ok_next;
                        state_next = S_IDLE;  // Return to idle after single-beat frame
                    end
                end else begin
                    m_axis_tvalid = 1'b0;
                    m_axis_tkeep  = '0;
                    m_axis_tlast  = 1'b0;
                    m_axis_tdata  = '0;
                end
            end

            // -------------------------------------------------------------
            // DATA
            // Pass data through and check CRC when TLAST is asserted
            // -------------------------------------------------------------
            S_DATA: begin
                if (s_axis_tvalid && s_axis_tlast) begin
                    // Last beat of the frame: perform CRC check
                    if (i_rx_fcs_valid) begin
                        crc_ok_next = (crc_calc == i_rx_fcs);
                    end else begin
                        crc_ok_next = 1'b0; // no FCS available → error
                    end
                    // Report CRC result on tuser
                    m_axis_tuser = crc_ok_next;
                    // Return to IDLE next cycle
                    state_next = S_IDLE;
                end else begin
                    // Middle of frame: tuser always 0
                    m_axis_tuser = 1'b0;
                end
            end

            // -------------------------------------------------------------
            // Default (should not occur)
            // -------------------------------------------------------------
            default: begin
                state_next    = S_IDLE;
                m_axis_tdata  = '0;
                m_axis_tkeep  = '0;
                m_axis_tvalid = 1'b0;
                m_axis_tlast  = 1'b0;
                m_axis_tuser  = 1'b0;
            end
        endcase
    end

    // =====================================================================
    // CRC Engine (Slicing-by-N)
    // Data and keep are fed directly into the CRC calculator.
    // FCS is provided separately; last 4 bytes of the stream do not
    // contain FCS, so CRC accumulates payload only.
    // =====================================================================
    slicing_crc #(
        .SLICE_LENGTH    (DATA_NBYTES),
        .INITIAL_CRC     (32'hFFFF_FFFF),
        .INVERT_OUTPUT   (1),
        .REGISTER_OUTPUT (0)   // combinational output
    ) u_rx_crc (
        .i_clk   (i_clk),
        .i_reset (crc_reset),
        .i_data  (s_axis_tdata),
        .i_valid (s_axis_tvalid ? s_axis_tkeep : '0),
        .o_crc   (crc_calc)
    );

endmodule

`default_nettype wire

