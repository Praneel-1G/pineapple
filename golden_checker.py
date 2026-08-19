# golden_checker.py
import os
import json
import importlib.util
from pathlib import Path

class GoldenChecker:
    def __init__(self, golden_script_path: Path):
        self.golden_script_path = golden_script_path
        self.golden_module = self._load_and_validate_model()

    def _load_and_validate_model(self):
        spec = importlib.util.spec_from_file_location("golden_model", self.golden_script_path)
        golden_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(golden_module)
        
        if not hasattr(golden_module, "compute"):
            raise ValueError("Golden model missing required function: compute(**kwargs)")
        return golden_module

    def verify_trace(self, trace_file: Path) -> dict:
        if not trace_file.exists():
            return {"status": "FATAL", "message": f"Trace file {trace_file.name} not found. Simulation crashed."}

        mismatches = []
        total_checks = 0

        with open(trace_file, 'r') as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line or not line.startswith("time="):
                    continue
                
                try:
                    tokens = line.split()
                    pairs = {}
                    for t in tokens:
                        if "=" in t:
                            k, v = t.split("=", 1)
                            try:
                                pairs[k] = int(v)
                            except ValueError:
                                pairs[k] = v
                    
                    sim_time = pairs.pop("time", 0)
                    
                    inputs = {}
                    actual = {}
                    for k, v in pairs.items():
                        if k.startswith("in_"):
                            inputs[k[3:]] = v
                        elif k.startswith("out_"):
                            actual[k[4:]] = v
                    
                    expected = self.golden_module.compute(**inputs)
                    
                    for out_port, expected_val in expected.items():
                        actual_val = actual.get(out_port)
                        if actual_val != expected_val:
                            mismatches.append({
                                "cycle": sim_time,
                                "inputs": inputs,
                                "expected": {out_port: expected_val},
                                "actual": {out_port: actual_val}
                            })

                    total_checks += 1
                except Exception as e:
                    return {"status": "ERROR", "message": f"Trace parse error on line {line_idx}: {str(e)}"}

        return {
            "status": "FAIL" if mismatches else "PASS",
            "total_checks": total_checks,
            "mismatches_found": len(mismatches),
            "mismatches": mismatches[:5]
        }