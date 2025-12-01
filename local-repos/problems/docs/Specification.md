# Simple Adder Specification

## Interface
- `clk`: Clock input (rising edge triggered)
- `a[7:0]`: 8-bit first operand
- `b[7:0]`: 8-bit second operand
- `sum[7:0]`: 8-bit addition result

## Behavior
On each rising clock edge, compute: `sum = a + b`

