import os

pkg_dir = "PINEAPPLE_DESIGN_PACKAGE/alu_8bit_v1"
os.makedirs(f"{pkg_dir}/rtl", exist_ok=True)
os.makedirs(f"{pkg_dir}/spec", exist_ok=True)
os.makedirs(f"{pkg_dir}/golden", exist_ok=True)
os.makedirs(f"{pkg_dir}/verification", exist_ok=True)

# FAULTY RTL: ADD opcode (0) mistakenly does XOR (^)
rtl = """module alu_8bit (
    input  logic clk,
    input  logic rst_n,
    input  logic [7:0] a,
    input  logic [7:0] b,
    input  logic [2:0] opcode,
    output logic [7:0] result,
    output logic valid_out
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result <= 8'h00;
            valid_out <= 1'b0;
        end else begin
            valid_out <= 1'b1;
            case (opcode)
                3'b000: result <= a ^ b; // <--- DELIBERATE BUG
                3'b001: result <= a - b;
                3'b010: result <= a & b;
                3'b011: result <= a | b;
                3'b100: result <= a ^ b;
                default: result <= 8'h00;
            endcase
        end
    end
endmodule
"""
with open(f"{pkg_dir}/rtl/design.sv", "w") as f: f.write(rtl)

spec = """# 8-bit ALU
Ports: clk, rst_n, a[7:0], b[7:0], opcode[2:0], result[7:0], valid_out.
Opcodes: 0=ADD, 1=SUB, 2=AND, 3=OR, 4=XOR.
Synchronous active-low reset."""
with open(f"{pkg_dir}/spec/specification.md", "w") as f: f.write(spec)

intent = "Test reset behavior. Test all opcodes with randomized inputs. Log trace as time=X a=Y b=Z opcode=W result=V valid_out=U"
with open(f"{pkg_dir}/verification/verification_intent.md", "w") as f: f.write(intent)

golden = """def compute(rst_n, a, b, opcode):
    if rst_n == 0: return {"result": 0, "valid_out": 0}
    res = 0
    if opcode == 0: res = (a + b) & 0xFF
    elif opcode == 1: res = (a - b) & 0xFF
    elif opcode == 2: res = a & b
    elif opcode == 3: res = a | b
    elif opcode == 4: res = a ^ b
    return {"result": res, "valid_out": 1}
"""
with open(f"{pkg_dir}/golden/golden.py", "w") as f: f.write(golden)

print("[+] Seeded faulty package: PINEAPPLE_DESIGN_PACKAGE/alu_8bit_v1")
