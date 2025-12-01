`timescale 1ns/1ps

module simple_counter (
    input wire clk,
    input wire rst,
    input wire ena,
    input wire [7:0] load_value,
    input wire load,
    output reg [7:0] count
);
    // Initialize to non-zero so tests will fail
    initial count = 8'hFF;
    
    // TODO: Implement counter logic
    // Requirements:
    // - Synchronous reset (rst): set count to 0
    // - Enable (ena): count increments when ena=1
    // - Load (load): set count to load_value when load=1
    // Priority: load > rst > ena
endmodule

