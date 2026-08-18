# master_generator.py
import requests
import json
import os
import shutil
import hashlib
from pathlib import Path

# --- THE STRICT JSON SCHEMA CONTRACT ---
PROTOCOL_VERSION = "1.0"
MASTER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["protocol_version", "design_id", "design", "metadata"],
    "properties": {
        "protocol_version": {"type": "string", "enum": [PROTOCOL_VERSION]},
        "design_id": {"type": "string"},
        "design": {
            "type": "object",
            "additionalProperties": False,
            "required": ["rtl", "specification", "golden_model", "verification_intent"],
            "properties": {
                "rtl": {"type": "string", "minLength": 1},
                "specification": {"type": "string", "minLength": 1},
                "golden_model": {"type": "string", "minLength": 1},
                "verification_intent": {"type": "string", "minLength": 1}
            }
        },
        "metadata": {"type": "object"}
    }
}

class MasterAgent:
    def __init__(self, model_name="qwen2.5-coder:3b"):
        self.model = model_name
        self.api_url = "http://localhost:11434/api/generate"
        self.system_prompt = """
You are the Pineapple Master Design Agent.
ROLE: You are a senior ASIC/RTL design engineer. 
Your job is to convert a hardware requirement into a candidate RTL design package.
You are the GENERATOR, not the verifier.

OUTPUT CONTRACT:
Return exactly one JSON object conforming to the supplied JSON schema.
Do not return Markdown code fences wrapping the JSON. Return raw JSON only.

REQUIREMENTS:
1. rtl: Synthesizable SystemVerilog.
2. specification: Markdown detailing ports, parameters, and behaviors.
3. golden_model: Deterministic Python. Must contain `def compute(**kwargs):`
4. verification_intent: Markdown detailing corner cases and functional objectives.

ENGINEERING CONSISTENCY:
Ensure port names, widths, and reset polarities perfectly match across all 4 files.
Do not intentionally introduce bugs unless instructed. Do not write testbenches.
"""

    def generate_design(self, requirement, design_id, output_root="PINEAPPLE_DESIGN_PACKAGE"):
        print(f"[*] Asking Master AI to generate: {design_id}")
        
        # 1. Ask Ollama to generate strictly conforming JSON
        payload = {
            "model": self.model,
            "system": self.system_prompt,
            "prompt": requirement,
            "stream": False,
            "format": MASTER_SCHEMA,  # <-- THIS ENFORCES THE STRUCTURE
            "options": {"temperature": 0.0, "seed": 42} # Deterministic mode
        }
        
        response = requests.post(self.api_url, json=payload).json()
        raw_text = response['response']
        
        # 2. Parse and Validate
        return self._validate_and_package(raw_text, design_id, Path(output_root))

    def _validate_and_package(self, raw_text, design_id, output_root):
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            print(f"[!] AI returned invalid JSON: {exc}")
            return None

        # 3. Artifact Validation (Basic Sanity Checks)
        golden = data["design"]["golden_model"]
        if "def compute(" not in golden:
            print("[!] Validation failed: Golden model missing 'compute(**kwargs)'")
            return None
            
        try:
            compile(golden, "<golden_model>", "exec") # Syntax check without executing
        except SyntaxError as exc:
            print(f"[!] Validation failed: Golden model has Python syntax errors: {exc}")
            return None

        # 4. Write the Package safely
        output_root.mkdir(parents=True, exist_ok=True)
        final_dir = output_root / design_id

        if final_dir.exists():
            shutil.rmtree(final_dir) # Clear previous run for demo purposes
            
        final_dir.mkdir()
        (final_dir / "rtl").mkdir()
        (final_dir / "spec").mkdir()
        (final_dir / "golden").mkdir()
        (final_dir / "verification").mkdir()

        self._write_file(final_dir / "rtl" / f"{design_id}.sv", data["design"]["rtl"])
        self._write_file(final_dir / "spec" / "specification.md", data["design"]["specification"])
        self._write_file(final_dir / "golden" / "golden.py", data["design"]["golden_model"])
        self._write_file(final_dir / "verification" / "verification_intent.md", data["design"]["verification_intent"])
        
        # Write metadata
        self._write_file(final_dir / "metadata.json", json.dumps(data["metadata"], indent=4))

        # 5. Generate Manifest
        manifest = self._create_manifest(final_dir)
        self._write_file(final_dir / "manifest.json", json.dumps(manifest, indent=4))

        return final_dir

    def _write_file(self, path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _create_manifest(self, package_dir):
        files_manifest = {}
        for path in package_dir.rglob("*"):
            if path.is_file():
                relative = str(path.relative_to(package_dir))
                with open(path, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                files_manifest[relative] = {
                    "sha256": file_hash,
                    "bytes": path.stat().st_size
                }
        
        return {
            "protocol_version": PROTOCOL_VERSION,
            "design_id": package_dir.name,
            "files": files_manifest
        }


# --- Execution --- (hardcoded test data so you can run the script immediately and see it work.)
if __name__ == "__main__":
    agent = MasterAgent()
    requirement = """
    Generate an 8-bit unsigned ALU with:
    - inputs a and b: 8-bit unsigned
    - opcode: 3 bits (000=ADD, 001=SUB, 010=AND, 011=OR, 100=XOR)
    - synchronous active-low reset (rst_n)
    - valid_out output
    - registered 8-bit result output
    """
    
    package_dir = agent.generate_design(requirement, "alu_8bit_v1")
    
    if package_dir:
        print(f"[*] Package ready at {package_dir}.")
        print("[*] Manifest generated with SHA-256 hashes.")
        print("[*] Ready to transmit to Verification Worker .")

#when we wire it up to take any user prompt:
"""
# --- Execution ---
if __name__ == "__main__":
    agent = MasterAgent()
    
    print("=== PINEAPPLE MASTER GENERATOR ===")
    design_id = input("Enter a Design ID (e.g., my_timer_v1): ").strip()
    
    print(f"\nEnter the hardware requirement for {design_id}.")
    print("(Type 'GENERATE' on a new line when finished):")
    
    user_lines = []
    while True:
        line = input()
        if line.strip().upper() == "GENERATE":
            break
        user_lines.append(line)
        
    requirement = "\n".join(user_lines)
    
    if not requirement.strip():
        print("[!] No requirement entered. Exiting.")
    else:
        package_dir = agent.generate_design(requirement, design_id)
        
        if package_dir:
            print(f"\n[*] SUCCESS: Package ready at {package_dir}.")
            print("[*] Manifest generated with SHA-256 hashes.")
            print("[*] Ready to transmit to Verification Worker (ASUS).")
"""