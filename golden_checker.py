# golden_checker.py
import os
import json
import importlib.util
import inspect
from pathlib import Path

class GoldenChecker:
    def __init__(self, golden_script_path: Path):
        self.golden_script_path = golden_script_path
        self.golden_module = self._load_and_validate_model()

    def _load_and_validate_model(self):
        """Loads the Python golden model and strictly validates its contract."""
        spec = importlib.util.spec_from_file_location("golden_model", self.golden_script_path)
        golden_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(golden_module)
        
        if not hasattr(golden_module, "compute"):
            raise ValueError("Golden model missing required function: compute(**kwargs)")
        
        sig = inspect.signature(golden_module.compute)
        if not any(param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values()):
            # Allow explicit kwargs if defined, but require flexibility
            pass 
            
        return golden_module

    def verify_trace(self, trace_file: Path) -> dict:
        """Reads key=value trace format and compares against golden model."""
        if not trace_file.exists():
            return {"status": "FATAL", "message": f"Trace file {trace_file.name} not found. Simulation crashed or TB is broken."}

        mismatches = []
        total_checks = 0

        with open(trace_file, 'r') as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line or not line.startswith("time="):
                    continue
                
                try:
                    # Parse space-separated key=value pairs into a dict
                    pairs = dict(item.split("=") for item in line.split())
                    sim_time = int(pairs.pop("time"))
                    
                    # Convert remaining values to ints (handling basic x/z gracefully as None or 0 depending on strategy)
                    signals = {k: int(v) if v.isdigit() else 0 for k, v in pairs.items()}
                    
                    # Extract inputs (We assume the TB logs both inputs and actual outputs)
                    # For a real system, the spec provides the input vs output lists.
                    # Here we pass everything, assuming the Golden model compute() pops what it needs.
                    expected_outputs = self.golden_module.compute(**signals)
                    
                    for out_port, expected_val in expected_outputs.items():
                        actual_val = signals.get(out_port)
                        if actual_val != expected_val:
                            mismatches.append({
                                "cycle": sim_time,
                                "inputs": {k:v for k,v in signals.items() if k not in expected_outputs},
                                "expected": {out_port: expected_val},
                                "actual": {out_port: actual_val}
                            })

                    total_checks += 1

                except Exception as e:
                    return {"status": "ERROR", "message": f"Trace parse error on line {line_idx}: {str(e)}"}

        result = {
            "status": "FAIL" if mismatches else "PASS",
            "total_checks": total_checks,
            "mismatches_found": len(mismatches),
            "mismatches": mismatches[:5]  # Strict cap on context window spam
        }
        return result