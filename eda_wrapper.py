# eda_wrapper.py
import subprocess
import os
from pathlib import Path

class EDARunner:
    def __init__(self, timeout_sec=30):
        self.timeout = timeout_sec

    def run_icarus(self, iteration_dir: Path, rtl_path: Path, tb_path: Path) -> dict:
        """Compiles RTL and TB. Artifacts live strictly in the iteration_dir."""
        executable = iteration_dir / "sim.vvp"
        log_file = iteration_dir / "compile.log"
        
        cmd = ["iverilog", "-g2012", "-o", str(executable), str(rtl_path), str(tb_path)]
        
        try:
            result = subprocess.run(cmd, cwd=iteration_dir, capture_output=True, text=True, timeout=self.timeout)
            
            with open(log_file, "w") as f:
                f.write(result.stdout + "\n" + result.stderr)
                
            return {
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "log": result.stderr if result.returncode != 0 else result.stdout
            }
        except subprocess.TimeoutExpired:
            return {"status": "FAIL", "log": "Icarus compiler timed out."}

    def run_simulation(self, iteration_dir: Path) -> dict:
        """Runs the compiled binary. Captures stdout and trace."""
        executable = iteration_dir / "sim.vvp"
        log_file = iteration_dir / "simulation.log"
        
        if not executable.exists():
            return {"status": "FAIL", "log": "Simulation binary not found. Compilation likely failed."}

        cmd = ["vvp", str(executable)]
        
        try:
            result = subprocess.run(cmd, cwd=iteration_dir, capture_output=True, text=True, timeout=self.timeout)
            
            with open(log_file, "w") as f:
                f.write(result.stdout)
                
            return {
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "log": result.stdout
            }
        except subprocess.TimeoutExpired:
            return {"status": "FAIL", "log": "Simulation timed out (possible infinite loop in TB)."}