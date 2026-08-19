from pathlib import Path

def setup_comb_medium():
    incoming_dir = Path("incoming/design")

    (incoming_dir / "rtl").mkdir(parents=True, exist_ok=True)
    (incoming_dir / "spec").mkdir(parents=True, exist_ok=True)
    (incoming_dir / "golden").mkdir(parents=True, exist_ok=True)

    # 8-bit ALU with seeded bug
    (incoming_dir / "rtl" / "design.sv").write_text("""module alu_8bit (
    input  logic [7:0] a,
    input  logic [7:0] b,
    input  logic [2:0] opcode,
    output logic [7:0] result
);
    always_comb begin
        case (opcode)
            3'b000: result = a ^ b; // SEEDED BUG: should be ADD
            3'b001: result = a - b;
            3'b010: result = a & b;
            3'b011: result = a | b;
            3'b100: result = a ^ b;
            default: result = 8'h00;
        endcase
    end
endmodule
""")

    (incoming_dir / "spec" / "specification.md").write_text("""# 8-bit ALU

Inputs:
- a: 8-bit
- b: 8-bit
- opcode: 3-bit

Output:
- result: 8-bit

Operations:
- 0 = ADD
- 1 = SUB
- 2 = AND
- 3 = OR
- 4 = XOR
""")

    (incoming_dir / "golden" / "golden.py").write_text("""def compute(a, b, opcode):
    if opcode == 0:
        result = (a + b) & 0xFF
    elif opcode == 1:
        result = (a - b) & 0xFF
    elif opcode == 2:
        result = a & b
    elif opcode == 3:
        result = a | b
    elif opcode == 4:
        result = a ^ b
    else:
        result = 0

    return {"result": result}
""")

    print(f"[+] Seeded COMB MEDIUM ALU into {incoming_dir.absolute()}")

if __name__ == "__main__":
    setup_comb_medium()