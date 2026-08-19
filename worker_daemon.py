# worker_daemon.py

import requests
import json
import shutil
import sys
import datetime
import re
from pathlib import Path

from eda_wrapper import EDARunner
from golden_checker import GoldenChecker


class VerificationAgent:

    def __init__(self, run_dir: Path, model_name="qwen2.5-coder:3b"):

        self.run_dir = run_dir
        self.iterations_dir = run_dir / "iterations"
        self.final_dir = run_dir / "final"
        self.report_dir = run_dir / "report"

        self.model = model_name
        self.api_url = "http://localhost:11434/api/generate"

        self.max_iterations = 3
        self.state = "INIT"

        # =====================================================
        # COMBINATIONAL-FIRST TESTBENCH PROMPT
        # =====================================================

        self.TB_SYSTEM_PROMPT = r"""
You are the Pineapple Prototype-1 Verification Agent.

Your ONLY task is to generate ONE simple, complete, compilable
SystemVerilog testbench for the EXACT RTL and specification supplied.

The testbench will be compiled with:

    iverilog -g2012 rtl.sv testbench.sv

and executed with:

    vvp sim.vvp

============================================================
PRIMARY GOAL
============================================================

For Prototype-1, prefer the SIMPLEST possible testbench.

Do NOT build UVM.
Do NOT build classes.
Do NOT build interfaces.
Do NOT build packages.
Do NOT build complicated verification infrastructure.

The goal is:

RTL
 ↓
simple TB
 ↓
Icarus
 ↓
VVP
 ↓
trace.txt
 ↓
Golden Model

============================================================
STEP 1 — READ THE RTL EXACTLY
============================================================

Before writing the testbench, inspect the RTL and determine:

1. Exact module name.
2. Exact input port names.
3. Exact output port names.
4. Exact port widths.
5. Whether the DUT is combinational.
6. Whether a clock actually exists.
7. Whether reset actually exists.

The RTL interface is authoritative.

DO NOT invent ports.

DO NOT invent clocks.

DO NOT invent resets.

DO NOT invent enable/valid/ready signals.

============================================================
PRIMARY PROTOTYPE-1 TARGET: COMBINATIONAL DUTS
============================================================

If the DUT is combinational:

- DO NOT generate a clock.
- DO NOT generate reset.
- DO NOT use @(posedge clk).
- DO NOT use @(negedge clk).
- DO NOT use sequential timing logic.
- DO NOT invent state.

The normal pattern is:

1. Drive inputs.
2. Wait #1.
3. Record outputs.
4. Repeat.
5. Close trace.
6. Finish.

============================================================
EXACT DUT CONNECTION RULE
============================================================

Declare local testbench signals corresponding to the DUT ports.

Example DUT:

module mux_2to1 (
    input logic a,
    input logic b,
    input logic sel,
    output logic y
);

The TB should use:

logic a;
logic b;
logic sel;
logic y;

Then instantiate:

mux_2to1 dut (
    .a(a),
    .b(b),
    .sel(sel),
    .y(y)
);

The local signals drive the DUT through the port connections.

============================================================
FORBIDDEN HIERARCHICAL INPUT DRIVING
============================================================

NEVER write:

    dut.a = a;
    dut.b = b;
    dut.sel = sel;

NEVER write:

    dut.a <= a;
    dut.b <= b;
    dut.sel <= sel;

Instead write:

    a = ...;
    b = ...;
    sel = ...;

============================================================
NO `include
============================================================

NEVER use:

    `include "design.sv"

The RTL is already compiled by the worker.

============================================================
MANDATORY TRACE FILE
============================================================

The testbench MUST create exactly:

    trace.txt

Declare:

    int fd;

Open it INSIDE the main initial block:

    fd = $fopen("trace.txt", "w");

Check the result:

    if (fd == 0) begin
        $display("ERROR: Could not open trace.txt");
        $finish;
    end

Use ONE file descriptor.

Do NOT repeatedly reopen trace.txt.

============================================================
MANDATORY TRACE FORMAT
============================================================

Every test transaction MUST write exactly one line.

Format:

    time=<time> in_<input>=<value> ... out_<output>=<value> ...

Example:

    time=1 in_a=5 in_b=3 in_opcode=0 out_result=8

Rules:

- Every input uses in_ prefix.
- Every output uses out_ prefix.
- Use exact RTL port names.
- Values must be decimal integers.
- Use %0t for time.
- Use %0d for signal values.
- Do NOT use JSON.
- Do NOT use hexadecimal trace values.
- Do NOT use binary trace values.
- Do NOT add extra fields.
- Do NOT omit DUT outputs.

============================================================
COMBINATIONAL TEST STRUCTURE
============================================================

Use this exact structural pattern:

module <dut_name>_tb;

    // Local DUT signals
    // ...

    int fd;

    // DUT instance
    <dut_name> dut (
        ...
    );

    initial begin

        fd = $fopen("trace.txt", "w");

        if (fd == 0) begin
            $display("ERROR: Could not open trace.txt");
            $finish;
        end

        // Test vector
        // Drive LOCAL TB signals
        // Wait
        #1;

        // Record result
        $fdisplay(
            fd,
            "...",
            ...
        );

        // More test vectors...

        $fclose(fd);
        $finish;

    end

endmodule

IMPORTANT:

ALL procedural statements such as:

    fd = $fopen(...);
    if (...)
    a = ...;
    #1;
    $fdisplay(...);
    $fclose(...);
    $finish;

MUST be INSIDE the initial block.

Do NOT put procedural statements directly at module scope.

============================================================
TEST VECTOR STRATEGY
============================================================

For small combinational designs, use approximately 8-20
deterministic directed tests.

Do NOT make the testbench huge.

Do NOT use uncontrolled randomization.

Do NOT use large exhaustive loops for Prototype-1.

Use meaningful values.

For arithmetic designs, prefer values such as:

0
1
2
3
7
15
16
31
63
64
127
128
254
255

For control designs, test every documented control selection.

For ALUs, test every documented opcode.

For multiplexers, test every input combination and select value.

For adders, include carry-producing cases and boundary cases.

For multipliers, include zero, one, small values, maximum values,
and representative large values.

============================================================
GOLDEN MODEL CONTRACT
============================================================

The Python Golden Model determines correctness.

The testbench does NOT need to calculate expected outputs itself.

The testbench only needs to:

1. apply legal inputs,
2. allow the combinational DUT to settle,
3. record inputs,
4. record outputs,
5. terminate.

Do NOT duplicate the Golden Model with assertions.

============================================================
DO NOT CHANGE THE RTL
============================================================

The RTL may intentionally contain a seeded bug.

Your job is to expose it.

Do NOT repair RTL inside the testbench.

============================================================
SIMULATION TERMINATION
============================================================

The testbench MUST terminate.

At the end:

    $fclose(fd);
    $finish;

Do NOT use:

    while (1)

Do NOT create an infinite stimulus loop.

Do NOT depend on timeout to stop simulation.

============================================================
ICARUS COMPATIBILITY
============================================================

Use simple SystemVerilog compatible with:

    iverilog -g2012

Prefer:

- module
- logic
- int
- initial
- always_comb if needed by TB
- $fopen
- $fdisplay
- $fclose
- $finish

Avoid:

- UVM
- classes
- packages
- interfaces
- DPI
- external libraries
- shell commands

============================================================
EXAMPLE — COMBINATIONAL MUX
============================================================

For:

module mux_2to1 (
    input logic a,
    input logic b,
    input logic sel,
    output logic y
);

A correct TB structure is:

module mux_2to1_tb;

    logic a;
    logic b;
    logic sel;
    logic y;

    int fd;

    mux_2to1 dut (
        .a(a),
        .b(b),
        .sel(sel),
        .y(y)
    );

    initial begin

        fd = $fopen("trace.txt", "w");

        if (fd == 0) begin
            $display("ERROR: Could not open trace.txt");
            $finish;
        end

        a = 0;
        b = 1;
        sel = 0;
        #1;

        $fdisplay(
            fd,
            "time=%0t in_a=%0d in_b=%0d in_sel=%0d out_y=%0d",
            $time,
            a,
            b,
            sel,
            y
        );

        a = 0;
        b = 1;
        sel = 1;
        #1;

        $fdisplay(
            fd,
            "time=%0t in_a=%0d in_b=%0d in_sel=%0d out_y=%0d",
            $time,
            a,
            b,
            sel,
            y
        );

        a = 1;
        b = 0;
        sel = 0;
        #1;

        $fdisplay(
            fd,
            "time=%0t in_a=%0d in_b=%0d in_sel=%0d out_y=%0d",
            $time,
            a,
            b,
            sel,
            y
        );

        a = 1;
        b = 0;
        sel = 1;
        #1;

        $fdisplay(
            fd,
            "time=%0t in_a=%0d in_b=%0d in_sel=%0d out_y=%0d",
            $time,
            a,
            b,
            sel,
            y
        );

        $fclose(fd);
        $finish;

    end

endmodule

Use this STYLE for other combinational DUTs.

============================================================
FINAL INTERNAL CHECK
============================================================

Before returning the testbench, silently verify:

[ ] Correct module name.
[ ] Correct input names.
[ ] Correct output names.
[ ] Correct port widths.
[ ] No invented clock.
[ ] No invented reset.
[ ] No hierarchical DUT input assignment.
[ ] Local TB signals are used.
[ ] DUT instantiated correctly.
[ ] int fd declared.
[ ] $fopen is inside initial.
[ ] $fdisplay is inside initial.
[ ] $fclose is inside initial.
[ ] $finish is inside initial.
[ ] trace.txt is created.
[ ] Every input begins with in_.
[ ] Every output begins with out_.
[ ] Trace uses decimal values.
[ ] Test vectors are deterministic.
[ ] Testbench terminates.
[ ] No `include.
[ ] Icarus -g2012 compatible.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Exactly two keys:

{
    "verification_plan": "...",
    "testbench_sv": "..."
}

No Markdown fences.
No text outside JSON.
No additional keys.

The testbench_sv field MUST contain the complete testbench.
"""


        # =====================================================
        # REPAIR PROMPT
        # =====================================================

        self.REPAIR_SYSTEM_PROMPT = r"""
You are the Pineapple Prototype-1 Diagnosis and Repair Agent.

Your job is to diagnose ONE verification failure.

You receive:

1. SPECIFICATION
2. CURRENT RTL
3. CURRENT TESTBENCH
4. EDA EVIDENCE
5. GOLDEN MODEL EVIDENCE, if available

The possible failure owners are:

- RTL
- TESTBENCH
- GOLDEN_MODEL
- SPECIFICATION
- ENVIRONMENT
- UNKNOWN

============================================================
MOST IMPORTANT RULE
============================================================

Do NOT repair RTL just because verification failed.

First inspect the CURRENT TESTBENCH and the deterministic evidence.

============================================================
FIRST CHECK THE TESTBENCH
============================================================

Check:

1. Correct DUT module name.
2. Correct DUT port names.
3. Correct port widths.
4. Local TB signals used for inputs.
5. No hierarchical DUT input assignments.
6. No invented clock.
7. No invented reset.
8. Correct trace file handling.
9. $fopen inside procedural block.
10. $fdisplay inside procedural block.
11. $fclose inside procedural block.
12. $finish inside procedural block.
13. Valid in_ trace fields.
14. Valid out_ trace fields.
15. Simulation terminates.

If any of these are wrong:

    REPAIR_TB

============================================================
COMPILATION FAILURE
============================================================

If Icarus compilation fails, inspect the actual compiler error.

If it is caused by the testbench:

    REPAIR_TB

Examples:

- wrong DUT instantiation
- wrong signal declaration
- invalid SystemVerilog
- procedural statement outside initial/always
- hierarchical assignment
- missing semicolon
- invalid testbench syntax

If the compiler clearly identifies invalid RTL syntax:

    REPAIR_RTL

Do not guess.

============================================================
SIMULATION FAILURE
============================================================

If simulation fails or times out:

First inspect the TESTBENCH.

Check:

- missing $finish
- infinite loop
- broken file handling
- invalid stimulus
- wrong DUT connections

If the testbench is responsible:

    REPAIR_TB

Only select REPAIR_RTL when the evidence directly supports an RTL
simulation problem.

============================================================
TRACE FAILURE
============================================================

If trace.txt is missing:

    REPAIR_TB

If trace.txt exists but is empty:

    REPAIR_TB

If trace.txt is malformed:

    REPAIR_TB

Do NOT diagnose an RTL logical bug without valid trace evidence.

============================================================
GOLDEN MISMATCH
============================================================

Only classify a functional RTL error when:

1. Icarus PASS.
2. VVP PASS.
3. trace.txt exists.
4. trace contains valid transactions.
5. DUT inputs are correct.
6. DUT outputs are correctly recorded.
7. Golden Model returns expected values.
8. Actual output differs from expected output.

Then:

    REPAIR_RTL

If the trace itself is wrong:

    REPAIR_TB

============================================================
MINIMAL RTL REPAIR
============================================================

If REPAIR_RTL:

- Return COMPLETE corrected RTL.
- Preserve module name.
- Preserve port names.
- Preserve port widths.
- Change only the demonstrated defect.
- Do not return a diff.
- Do not return partial code.
- Do not use Markdown fences.

============================================================
MINIMAL TB REPAIR
============================================================

If REPAIR_TB:

- Return COMPLETE corrected TB.
- Match CURRENT RTL exactly.
- Use local TB signals.
- Never drive DUT inputs hierarchically.
- Preserve correct existing tests.
- Fix only the demonstrated TB problem.
- Keep the TB simple.
- Ensure trace.txt is generated.
- Ensure $finish exists.

============================================================
CURRENT RTL RULE
============================================================

Always use the CURRENT RTL supplied in the current iteration.

Do not repair the original RTL if it has already been repaired.

============================================================
BLOCK
============================================================

Use BLOCK only when:

- specification and Golden Model conflict
- requirements are contradictory
- safe diagnosis is impossible

============================================================
OUTPUT
============================================================

Return ONLY valid JSON:

{
    "action": "REPAIR_RTL | REPAIR_TB | BLOCK | REQUEST_MORE_EVIDENCE",
    "diagnosis": "...",
    "bug_class": "...",
    "repair_summary": "...",
    "repaired_rtl": "...",
    "repaired_testbench_sv": "..."
}

If REPAIR_RTL:

    repaired_rtl = complete corrected RTL
    repaired_testbench_sv = ""

If REPAIR_TB:

    repaired_rtl = ""
    repaired_testbench_sv = complete corrected TB

If BLOCK:

    repaired_rtl = ""
    repaired_testbench_sv = ""

If REQUEST_MORE_EVIDENCE:

    repaired_rtl = ""
    repaired_testbench_sv = ""

Never omit keys.
Never add keys.
Never use Markdown.
"""


    # =========================================================
    # OLLAMA
    # =========================================================

    def _call_ollama(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:

        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "seed": 42
            }
        }

        try:

            response = requests.post(
                self.api_url,
                json=payload,
                timeout=600
            )

            response.raise_for_status()

            data = response.json()

            if "response" not in data:
                raise RuntimeError(
                    "Ollama response missing 'response'."
                )

            return json.loads(
                data["response"]
            )

        except (
            requests.RequestException,
            json.JSONDecodeError,
            KeyError
        ) as e:

            raise RuntimeError(
                f"Ollama API Failure: {e}"
            )


    # =========================================================
    # MAIN VERIFICATION LOOP
    # =========================================================

    def run_continuous_verification(
        self,
        input_dir: Path
    ):

        self.state = "PACKAGE_VALIDATION"

        print(
            f"\n[{self.state}] "
            "Validating incoming design snapshot..."
        )

        rtl_path = (
            input_dir
            / "rtl"
            / "design.sv"
        )

        spec_path = (
            input_dir
            / "spec"
            / "specification.md"
        )

        golden_path = (
            input_dir
            / "golden"
            / "golden.py"
        )

        if not all(
            p.exists()
            for p in [
                rtl_path,
                spec_path,
                golden_path
            ]
        ):

            print(
                "[!] FATAL: Invalid package structure."
            )

            return False

        current_rtl = rtl_path.read_text()
        spec = spec_path.read_text()

        try:

            golden = GoldenChecker(
                golden_path
            )

        except Exception as e:

            print(
                f"[!] FATAL: Golden model error: {e}"
            )

            return False

        eda = EDARunner()

        # =====================================================
        # GENERATE TESTBENCH
        # =====================================================

        self.state = "GENERATE_TB"

        print(
            f"[{self.state}] "
            "AI generating verification plan and testbench..."
        )

        try:

            tb_data = self._call_ollama(
                self.TB_SYSTEM_PROMPT,
                f"SPEC:\n{spec}\n\nRTL:\n{current_rtl}"
            )

        except Exception as e:

            print(
                f"[!] FATAL: TB generation failed: {e}"
            )

            return False

        current_tb = tb_data.get(
            "testbench_sv",
            ""
        )

        v_plan = tb_data.get(
            "verification_plan",
            "No verification plan generated."
        )

        if not current_tb.strip():

            print(
                "[!] FATAL: AI returned an empty testbench."
            )

            return False

        last_rtl_path = None
        last_tb_path = None
        last_trace_path = None

        # =====================================================
        # ITERATIONS
        # =====================================================

        for iteration in range(
            1,
            self.max_iterations + 1
        ):

            iter_dir = (
                self.iterations_dir
                / f"iteration_{iteration:03d}"
            )

            iter_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            iter_rtl_path = (
                iter_dir / "rtl.sv"
            )

            iter_tb_path = (
                iter_dir / "testbench.sv"
            )

            plan_path = (
                iter_dir
                / "verification_plan.md"
            )

            trace_path = (
                iter_dir
                / "trace.txt"
            )

            # Remove stale trace.
            if trace_path.exists():
                trace_path.unlink()

            iter_rtl_path.write_text(
                current_rtl
            )

            iter_tb_path.write_text(
                current_tb
            )

            plan_path.write_text(
                v_plan
            )

            last_rtl_path = (
                iter_rtl_path
            )

            last_tb_path = (
                iter_tb_path
            )

            last_trace_path = (
                trace_path
            )

            print(
                f"\n=== ITERATION "
                f"{iteration} ==="
            )

            # =================================================
            # COMPILE
            # =================================================

            self.state = "COMPILING"

            comp_res = eda.run_icarus(
                iter_dir,
                iter_rtl_path,
                iter_tb_path
            )

            self._save_iteration_result(
                iter_dir,
                "compile",
                comp_res["status"],
                comp_res["log"]
            )

            if comp_res["status"] == "FAIL":

                evidence = (
                    "STAGE: COMPILATION FAILED\n"
                    f"LOG:\n{comp_res['log']}"
                )

                current_rtl, current_tb = (
                    self._diagnose_and_repair(
                        evidence,
                        current_rtl,
                        current_tb,
                        spec,
                        iter_dir
                    )
                )

                if current_rtl is None:
                    break

                continue

            # =================================================
            # SIMULATE
            # =================================================

            self.state = "SIMULATING"

            sim_res = eda.run_simulation(
                iter_dir
            )

            self._save_iteration_result(
                iter_dir,
                "simulation",
                sim_res["status"],
                sim_res["log"]
            )

            if sim_res["status"] == "FAIL":

                evidence = (
                    "STAGE: SIMULATION FAILED\n"
                    f"RETURN CODE: "
                    f"{sim_res.get('returncode')}\n"
                    f"STDOUT:\n"
                    f"{sim_res.get('stdout', '')}\n"
                    f"STDERR:\n"
                    f"{sim_res.get('stderr', '')}\n"
                    f"LOG:\n"
                    f"{sim_res.get('log', '')}"
                )

                current_rtl, current_tb = (
                    self._diagnose_and_repair(
                        evidence,
                        current_rtl,
                        current_tb,
                        spec,
                        iter_dir
                    )
                )

                if current_rtl is None:
                    break

                continue

            # =================================================
            # TRACE CHECK
            # =================================================

            if not trace_path.exists():

                evidence = (
                    "STAGE: TRACE MISSING\n"
                    "Icarus compilation succeeded.\n"
                    "VVP simulation succeeded.\n"
                    "trace.txt was not produced.\n"
                    "This is primarily a testbench problem."
                )

                gold_res = {
                    "status": "FATAL",
                    "message": (
                        "trace.txt was not produced."
                    )
                }

                self._save_json(
                    iter_dir / "result.json",
                    gold_res
                )

                current_rtl, current_tb = (
                    self._diagnose_and_repair(
                        evidence,
                        current_rtl,
                        current_tb,
                        spec,
                        iter_dir
                    )
                )

                if current_rtl is None:
                    break

                continue

            # =================================================
            # GOLDEN CHECK
            # =================================================

            self.state = "GOLDEN_CHECK"

            gold_res = (
                golden.verify_trace(
                    trace_path
                )
            )

            self._save_json(
                iter_dir / "result.json",
                gold_res
            )

            if gold_res["status"] == "PASS":

                self.state = "VERIFIED_PASS"

                print(
                    f"[{self.state}] "
                    f"RTL matches Golden Model "
                    f"({gold_res['total_checks']} checks)."
                )

                self._finalize_run(
                    "PASS",
                    last_rtl_path,
                    last_tb_path,
                    trace_path
                )

                return True

            # =================================================
            # GOLDEN ERROR / MISMATCH
            # =================================================

            if gold_res["status"] in (
                "FATAL",
                "ERROR"
            ):

                evidence = (
                    f"STAGE: GOLDEN CHECK "
                    f"{gold_res['status']}\n"
                    f"MESSAGE:\n"
                    f"{gold_res.get('message', 'Unknown Golden error.')}"
                )

            else:

                evidence = (
                    "STAGE: FUNCTIONAL MISMATCH\n"
                    "MISMATCHES:\n"
                    + json.dumps(
                        gold_res.get(
                            "mismatches",
                            []
                        ),
                        indent=2
                    )
                )

            self.state = "DIAGNOSING"

            print(
                f"[{self.state}] "
                "Failures detected. "
                "AI classifying and repairing..."
            )

            current_rtl, current_tb = (
                self._diagnose_and_repair(
                    evidence,
                    current_rtl,
                    current_tb,
                    spec,
                    iter_dir
                )
            )

            if current_rtl is None:
                break

        # =====================================================
        # UNRESOLVED
        # =====================================================

        self.state = "UNRESOLVED"

        print(
            f"\n[{self.state}] "
            "Verification budget exhausted "
            "or AI blocked repair."
        )

        self._finalize_run(
            "UNRESOLVED",
            last_rtl_path,
            last_tb_path,
            last_trace_path
        )

        return False


    # =========================================================
    # DIAGNOSIS AND REPAIR
    # =========================================================

    def _diagnose_and_repair(
        self,
        evidence: str,
        rtl: str,
        tb: str,
        spec: str,
        iter_dir: Path
    ):

        prompt = (
            f"SPECIFICATION:\n{spec}\n\n"
            f"CURRENT RTL:\n{rtl}\n\n"
            f"CURRENT TESTBENCH:\n{tb}\n\n"
            f"DETERMINISTIC EVIDENCE:\n{evidence}"
        )

        data = self._call_ollama(
            self.REPAIR_SYSTEM_PROMPT,
            prompt
        )

        self._save_json(
            iter_dir / "diagnosis.json",
            data
        )

        action = data.get(
            "action",
            "BLOCK"
        )

        print(
            "[AI DIAGNOSIS] "
            f"{data.get('diagnosis', 'No diagnosis provided')}"
        )

        print(
            "[AI BUG CLASS] "
            f"{data.get('bug_class', 'unknown')}"
        )

        print(
            "[AI ACTION] "
            f"{action}"
        )

        if action == "REPAIR_RTL":

            repaired = data.get(
                "repaired_rtl",
                ""
            ).strip()

            if not repaired:

                print(
                    "[!] AI selected REPAIR_RTL "
                    "but returned empty RTL."
                )

                return None, None

            return repaired, tb

        elif action == "REPAIR_TB":

            repaired_tb = data.get(
                "repaired_testbench_sv",
                ""
            ).strip()

            if not repaired_tb:

                print(
                    "[!] AI selected REPAIR_TB "
                    "but returned empty TB."
                )

                return None, None

            return rtl, repaired_tb

        else:

            print(
                "[!] AI blocked repair "
                "or requested more evidence."
            )

            return None, None


    # =========================================================
    # SAVE HELPERS
    # =========================================================

    def _save_iteration_result(
        self,
        iter_dir: Path,
        stage: str,
        status: str,
        log: str
    ):

        self._save_json(
            iter_dir
            / f"{stage}_result.json",
            {
                "stage": stage,
                "status": status,
                "log": log
            }
        )

    def _save_json(
        self,
        path: Path,
        data: dict
    ):

        with open(
            path,
            "w"
        ) as f:

            json.dump(
                data,
                f,
                indent=4
            )


    # =========================================================
    # FINAL REPORT
    # =========================================================

    def _finalize_run(
        self,
        status: str,
        final_rtl: Path,
        final_tb: Path,
        trace_path: Path
    ):

        self.final_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.report_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        if (
            final_rtl
            and final_rtl.exists()
        ):

            shutil.copy(
                final_rtl,
                self.final_dir
                / "final_rtl.sv"
            )

        if (
            final_tb
            and final_tb.exists()
        ):

            shutil.copy(
                final_tb,
                self.final_dir
                / "final_testbench.sv"
            )

        if (
            trace_path
            and trace_path.exists()
        ):

            shutil.copy(
                trace_path,
                self.final_dir
                / "final_trace.txt"
            )

        report_data = {
            "timestamp":
                datetime.datetime.now().isoformat(),

            "final_status":
                status,

            "run_directory":
                str(self.run_dir)
        }

        self._save_json(
            self.report_dir
            / "final_report.json",
            report_data
        )

        md_report = f"""# Pineapple Verification Report

- **Timestamp**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Final Status**: `{status}`
- **Run Directory**: `{self.run_dir}`

## Artifacts

- **Final RTL**: `final/final_rtl.sv`
- **Final Testbench**: `final/final_testbench.sv`
- **Trace Output**: `final/final_trace.txt`
"""

        (
            self.report_dir
            / "final_report.md"
        ).write_text(
            md_report
        )

        design_name = (
            self.run_dir.name
            .split("_")[-1]
            .upper()
        )

        print()
        print("=" * 50)
        print(
            "PINEAPPLE VERIFICATION COMPLETE"
        )
        print("=" * 50)
        print(
            f"Design: {design_name}"
        )
        print(
            f"Status: {status}"
        )
        print()
        print(
            f"Run Folder:\n"
            f"{self.run_dir}/"
        )
        print()
        print(
            f"Final RTL:\n"
            f"{self.final_dir}/final_rtl.sv"
        )
        print()
        print(
            f"Final Testbench:\n"
            f"{self.final_dir}/final_testbench.sv"
        )
        print()
        print(
            f"Report:\n"
            f"{self.report_dir}/final_report.md"
        )
        print(
            "=" * 50
        )


# =============================================================
# MAIN
# =============================================================

if __name__ == "__main__":

    incoming_design = Path(
        "incoming/design"
    )

    if (
        not incoming_design.exists()
        or not (
            incoming_design
            / "rtl"
            / "design.sv"
        ).exists()
    ):

        print(
            "[!] Error: No design found in "
            "incoming/design/. "
            "Populate it before running."
        )

        sys.exit(1)

    design_code = (
        incoming_design
        / "rtl"
        / "design.sv"
    ).read_text()

    match = re.search(
        r"module\s+([a-zA-Z0-9_]+)",
        design_code
    )

    design_name = (
        match.group(1)
        if match
        else "unknown_design"
    )

    timestamp = (
        datetime.datetime.now()
        .strftime("%Y%m%d_%H%M%S")
    )

    run_id = (
        f"{timestamp}_{design_name}"
    )

    run_root = (
        Path("runs")
        / run_id
    )

    run_root.mkdir(
        parents=True,
        exist_ok=True
    )

    (run_root / "input").mkdir(
        parents=True,
        exist_ok=True
    )

    (run_root / "iterations").mkdir(
        parents=True,
        exist_ok=True
    )

    (run_root / "final").mkdir(
        parents=True,
        exist_ok=True
    )

    (run_root / "report").mkdir(
        parents=True,
        exist_ok=True
    )

    # Freeze current input design.
    shutil.copytree(
        incoming_design / "rtl",
        run_root / "input" / "rtl",
        dirs_exist_ok=True
    )

    shutil.copytree(
        incoming_design / "spec",
        run_root / "input" / "spec",
        dirs_exist_ok=True
    )

    shutil.copytree(
        incoming_design / "golden",
        run_root / "input" / "golden",
        dirs_exist_ok=True
    )

    print(
        "[*] Created immutable run snapshot at:"
    )

    print(
        f"{run_root}"
    )

    agent = VerificationAgent(
        run_root
    )

    agent.run_continuous_verification(
        run_root / "input"
    )