# eda_wrapper.py

import subprocess
from pathlib import Path


class EDARunner:

    def __init__(self, timeout_sec=30):
        self.timeout = timeout_sec

    def run_icarus(self, iteration_dir: Path, rtl_path: Path, tb_path: Path) -> dict:

        executable = iteration_dir / "sim.vvp"
        log_file = iteration_dir / "compile.log"

        # Because cwd=iteration_dir, use only local filenames.
        cmd = [
            "iverilog",
            "-g2012",
            "-o",
            "sim.vvp",
            rtl_path.name,
            tb_path.name,
        ]

        try:

            result = subprocess.run(
                cmd,
                cwd=iteration_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            combined_log = (
                "=== STDOUT ===\n"
                + result.stdout
                + "\n=== STDERR ===\n"
                + result.stderr
            )

            log_file.write_text(
                combined_log,
                encoding="utf-8",
            )

            return {
                "status": (
                    "PASS"
                    if result.returncode == 0
                    else "FAIL"
                ),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "log": combined_log,
            }

        except subprocess.TimeoutExpired:

            message = "Icarus compilation timed out."

            log_file.write_text(
                message,
                encoding="utf-8",
            )

            return {
                "status": "FAIL",
                "returncode": None,
                "stdout": "",
                "stderr": message,
                "log": message,
            }

    def run_simulation(self, iteration_dir: Path) -> dict:

        executable = iteration_dir / "sim.vvp"
        log_file = iteration_dir / "simulation.log"

        if not executable.exists():

            message = (
                "sim.vvp was not found. "
                "Compilation did not produce the simulation binary."
            )

            log_file.write_text(
                message,
                encoding="utf-8",
            )

            return {
                "status": "FAIL",
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "log": message,
            }

        # IMPORTANT:
        # cwd is already iteration_dir, so use ONLY sim.vvp.
        cmd = [
            "vvp",
            "sim.vvp",
        ]

        try:

            result = subprocess.run(
                cmd,
                cwd=iteration_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            combined_log = (
                "=== STDOUT ===\n"
                + result.stdout
                + "\n=== STDERR ===\n"
                + result.stderr
            )

            log_file.write_text(
                combined_log,
                encoding="utf-8",
            )

            return {
                "status": (
                    "PASS"
                    if result.returncode == 0
                    else "FAIL"
                ),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "log": combined_log,
            }

        except subprocess.TimeoutExpired:

            message = (
                "Simulation timed out. "
                "Possible infinite loop or missing $finish."
            )

            log_file.write_text(
                message,
                encoding="utf-8",
            )

            return {
                "status": "FAIL",
                "returncode": None,
                "stdout": "",
                "stderr": message,
                "log": message,
            }