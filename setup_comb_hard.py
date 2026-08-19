from pathlib import Path

def setup_comb_hard():
    incoming_dir = Path("incoming/design")

    (incoming_dir / "rtl").mkdir(parents=True, exist_ok=True)
    (incoming_dir / "spec").mkdir(parents=True, exist_ok=True)
    (incoming_dir / "golden").mkdir(parents=True, exist_ok=True)

    # 8x8 multiplier with seeded bug
    (incoming_dir / "rtl" / "design.sv").write_text("""module multiplier_8x8 (
    input  logic [7:0] a,
    input  logic [7:0] b,
    output logic [15:0] product
);
    always_comb begin
        product = (a * b) + 1; // SEEDED BUG: extra +1
    end
endmodule
""")

    (incoming_dir / "spec" / "specification.md").write_text("""# 8x8 Unsigned Multiplier

Inputs:
- a: unsigned 8-bit
- b: unsigned 8-bit

Output:
- product: unsigned 16-bit

Required behavior:
product = a * b
""")

    (incoming_dir / "golden" / "golden.py").write_text("""def compute(a, b):
    return {
        "product": (a * b) & 0xFFFF
    }
""")

    print(f"[+] Seeded COMB HARD multiplier into {incoming_dir.absolute()}")

if __name__ == "__main__":
    setup_comb_hard()