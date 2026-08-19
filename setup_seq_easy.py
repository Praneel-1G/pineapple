from pathlib import Path

def setup_seq_easy():
    incoming_dir = Path("incoming/design")

    (incoming_dir / "rtl").mkdir(parents=True, exist_ok=True)
    (incoming_dir / "spec").mkdir(parents=True, exist_ok=True)
    (incoming_dir / "golden").mkdir(parents=True, exist_ok=True)

    # 4-bit counter with seeded bug
    (incoming_dir / "rtl" / "design.sv").write_text("""module counter_4bit (
    input  logic clk,
    input  logic rst_n,
    output logic [3:0] count
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= 4'h0;
        else
            count <= count + 4'd2; // SEEDED BUG: should increment by 1
    end
endmodule
""")

    (incoming_dir / "spec" / "specification.md").write_text("""# 4-bit Counter

Inputs:
- clk: clock
- rst_n: active-low asynchronous reset

Output:
- count: 4-bit counter

Required behavior:
- When rst_n = 0, count = 0.
- On every rising edge of clk while rst_n = 1,
  count increments by 1.
- Counter wraps around after 15.
""")

    (incoming_dir / "golden" / "golden.py").write_text("""def compute(rst_n, count):
    if rst_n == 0:
        return {"count": 0}

    return {
        "count": (count + 1) & 0xF
    }
""")

    print(f"[+] Seeded SEQ EASY counter into {incoming_dir.absolute()}")

if __name__ == "__main__":
    setup_seq_easy()