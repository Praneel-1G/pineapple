# Pineapple 🍍: AI-Assisted Closed-Loop RTL Verification

Pineapple is a distributed, AI-assisted RTL engineering system. In this architecture, a **Master AI** generates candidate hardware designs, specifications, and reference models. An independent **Verification Worker** then autonomously constructs testbenches, executes deterministic EDA simulation, cross-checks results against the reference model, diagnoses failures, proposes RTL/TB repairs, and performs regression testing.

**Core Philosophy: The AI is the Assistant; Deterministic EDA is the Judge.**
The AI generates the candidate and the tests, but `Icarus Verilog` and the `Python Golden Model` decide what is actually true. 

## 🏗️ System Architecture

Pineapple enforces a strict separation of concerns between the Generator and the Verifier, preventing the AI from falsely validating its own incorrect code.

```text
                 [ MASTER GENERATOR ]
                 (LLM: Qwen2.5-Coder)
                          │
            Generates: RTL, Spec, Golden Model
                          │
                          ▼
            { STRUCTURED DESIGN PACKAGE }
                          │
                          ▼
                [ VERIFICATION WORKER ]
                (LLM: Qwen2.5-Coder)
                          │
                 1. Analyzes Package
                 2. Generates SystemVerilog Testbench
                          │
                          ▼
                 [ DETERMINISTIC EDA ]
             (Icarus Verilog + Python Checker)
                          │
           ┌──────────────┴──────────────┐
           │                             │
        [ PASS ]                      [ FAIL ]
           │                             │
           ▼                             ▼
      Run Regressions            AI Diagnoses Logs & Trace
           │                             │
           ▼                             ▼
    FINAL REPORT OUT             Proposes RTL/TB Repair
                                         │
                                         ▼
                                     Recompile