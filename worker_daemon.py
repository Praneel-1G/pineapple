# worker_daemon.py
import requests
import json
import shutil
import hashlib
from pathlib import Path
from eda_wrapper import EDARunner
from golden_checker import GoldenChecker
from verification_schemas import TB_GENERATION_SCHEMA, REPAIR_SCHEMA

class VerificationAgent:
    def __init__(self, workspace: Path, model_name="qwen2.5-coder:3b"):
        self.workspace = workspace
        self.model = model_name
        self.api_url = "http://localhost:11434/api/generate"
        self.max_iterations = 3
        self.state = "INIT"

        self.TB_SYSTEM_PROMPT = """
You are the Pineapple Verification Agent.
Read the RTL and Specification. Write a SystemVerilog testbench.
CRITICAL: You MUST write your trace to 'trace.txt' using space-separated key=value pairs.
Example Verilog: $fdisplay(fd, "time=%0t a=%0d b=%0d result=%0d", $time, a, b, result);
Return exactly the JSON schema requested.
"""
        self.REPAIR_SYSTEM_PROMPT = """
You are the Pineapple Diagnosis & Repair Agent.
You will be provided with structured verification evidence containing RTL, TB, and EDA logs/mismatches.
Determine if the failure is in the RTL or the Testbench.
If RTL is broken, return action="REPAIR_RTL" and provide the fixed RTL.
If TB is broken, return action="REPAIR_TB" and provide the fixed TB.
If the evidence is conflicting, return action="BLOCK".
"""

    def _call_ollama(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0.0, "seed": 42}
        }
        try:
            response = requests.post(self.api_url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return json.loads(data['response'])
        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Ollama API Failure: {e}")

    def run_continuous_verification(self, package_dir: Path):
        self.state = "PACKAGE_VALIDATION"
        print(f"\n[{self.state}] Validating package: {package_dir.name}")
        
        rtl_path = package_dir / "rtl" / "design.sv"
        spec_path = package_dir / "spec" / "specification.md"
        golden_path = package_dir / "golden" / "golden.py"
        
        if not all(p.exists() for p in [rtl_path, spec_path, golden_path]):
            print("[!] FATAL: Invalid package structure.")
            return False

        current_rtl = rtl_path.read_text()
        current_tb = ""
        spec = spec_path.read_text()
        
        golden = GoldenChecker(golden_path)
        eda = EDARunner()

        self.state = "GENERATE_TB"
        print(f"[{self.state}] AI generating verification plan and testbench...")
        tb_data = self._call_ollama(self.TB_SYSTEM_PROMPT, f"SPEC:\n{spec}\n\nRTL:\n{current_rtl}", TB_GENERATION_SCHEMA)
        current_tb = tb_data["testbench_sv"]

        for iteration in range(1, self.max_iterations + 1):
            iter_dir = self.workspace / f"iteration_{iteration:03d}"
            iter_dir.mkdir(parents=True)
            
            # Save artifacts for this specific iteration
            iter_rtl_path = iter_dir / f"rtl_iter_{iteration:03d}.sv"
            iter_tb_path = iter_dir / f"tb_iter_{iteration:03d}.sv"
            iter_rtl_path.write_text(current_rtl)
            iter_tb_path.write_text(current_tb)

            print(f"\n=== ITERATION {iteration} ===")
            
            # --- COMPILE ---
            self.state = "COMPILING"
            comp_res = eda.run_icarus(iter_dir, iter_rtl_path, iter_tb_path)
            
            if comp_res["status"] == "FAIL":
                evidence = f"STAGE: COMPILATION FAILED\nLOG:\n{comp_res['log']}"
                current_rtl, current_tb = self._diagnose_and_repair(evidence, current_rtl, current_tb, spec)
                continue

            # --- SIMULATE ---
            self.state = "SIMULATING"
            sim_res = eda.run_simulation(iter_dir)
            
            if sim_res["status"] == "FAIL":
                evidence = f"STAGE: SIMULATION CRASHED\nLOG:\n{sim_res['log']}"
                current_rtl, current_tb = self._diagnose_and_repair(evidence, current_rtl, current_tb, spec)
                continue

            # --- GOLDEN CROSS-CHECK ---
            self.state = "GOLDEN_CHECK"
            trace_path = iter_dir / "trace.txt"
            gold_res = golden.verify_trace(trace_path)

            if gold_res["status"] == "PASS":
                self.state = "VERIFIED_PASS"
                print(f"[{self.state}] RTL matches Golden Model perfectly ({gold_res['total_checks']} checks).")
                self._write_final_report("PASS", iter_rtl_path, iter_tb_path)
                return True
                
            elif gold_res["status"] == "FATAL":
                # Missing trace file means TB logic is wrong
                evidence = f"STAGE: GOLDEN CHECK FATAL\nLOG: {gold_res['message']}"
            else:
                # Actual functional mismatches
                evidence = f"STAGE: FUNCTIONAL MISMATCH\nMISMATCHES:\n{json.dumps(gold_res['mismatches'], indent=2)}"

            self.state = "DIAGNOSING"
            print(f"[{self.state}] Failures detected. AI classifying and repairing...")
            current_rtl, current_tb = self._diagnose_and_repair(evidence, current_rtl, current_tb, spec)
            
            if current_rtl is None:
                break # AI requested a BLOCK or gave up

        self.state = "UNRESOLVED"
        print(f"\n[{self.state}] Verification Budget Exhausted.")
        self._write_final_report("UNRESOLVED", iter_rtl_path, iter_tb_path)
        return False

    def _diagnose_and_repair(self, evidence: str, rtl: str, tb: str, spec: str):
        prompt = f"SPECIFICATION:\n{spec}\n\nRTL:\n{rtl}\n\nTESTBENCH:\n{tb}\n\nEVIDENCE:\n{evidence}"
        
        data = self._call_ollama(self.REPAIR_SYSTEM_PROMPT, prompt, REPAIR_SCHEMA)
        
        print(f"[AI DIAGNOSIS] {data['diagnosis']} (Class: {data['bug_class']})")
        print(f"[AI ACTION] {data['action']}")
        
        if data["action"] == "REPAIR_RTL":
            return data["repaired_rtl"], tb
        elif data["action"] == "REPAIR_TB":
            return rtl, data["repaired_testbench_sv"]
        else:
            print("[!] AI blocked repair or requested more evidence. Halting loop.")
            return None, None

    def _write_final_report(self, status: str, final_rtl: Path, final_tb: Path):
        report = {
            "final_status": status,
            "final_rtl_file": str(final_rtl),
            "final_tb_file": str(final_tb)
        }
        with open(self.workspace / "final_report.json", "w") as f:
            json.dump(report, f, indent=4)
        print("[*] Dashboard payload ready.")

if __name__ == "__main__":
    pkg = Path("PINEAPPLE_DESIGN_PACKAGE/alu_8bit_v1")
    wrk = Path("worker_active_run")
    
    # Clean workspace for fresh demo run
    if wrk.exists():
        shutil.rmtree(wrk)
    wrk.mkdir()
    
    agent = VerificationAgent(wrk)
    agent.run_continuous_verification(pkg)