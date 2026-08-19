from pathlib import Path

def setup_comb_easy():
    incoming_dir = Path("incoming/design")

    (incoming_dir / "rtl").mkdir(parents=True, exist_ok=True)
    (incoming_dir / "spec").mkdir(parents=True, exist_ok=True)
    (incoming_dir / "golden").mkdir(parents=True, exist_ok=True)

    # Simple 2:1 MUX with seeded bug
    (incoming_dir / "rtl" / "design.sv").write_text("""module mux_2to1 (
    input  logic a,
    input  logic b,
    input  logic sel,
    output logic y
);
    always_comb begin
        if (sel)
            y = a;       // SEEDED BUG: should select b when sel=1
        else
            y = b;
    end
endmodule
""")

    (incoming_dir / "spec" / "specification.md").write_text("""# 2:1 Multiplexer

Inputs:
- a: 1-bit
- b: 1-bit
- sel: 1-bit

Output:
- y: 1-bit

Required behavior:
- sel = 0 -> y = a
- sel = 1 -> y = b
""")

    (incoming_dir / "golden" / "golden.py").write_text("""def compute(a, b, sel):
    if sel == 0:
        y = a
    else:
        y = b

    return {"y": y}
""")

    print(f"[+] Seeded COMB EASY MUX into {incoming_dir.absolute()}")

if __name__ == "__main__":
    setup_comb_easy()