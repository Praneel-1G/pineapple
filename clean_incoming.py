# clean_incoming.py
import shutil
from pathlib import Path

def clean():
    incoming = Path("incoming/design")
    if incoming.exists():
        shutil.rmtree(incoming)
    
    (incoming / "rtl").mkdir(parents=True, exist_ok=True)
    (incoming / "spec").mkdir(parents=True, exist_ok=True)
    (incoming / "golden").mkdir(parents=True, exist_ok=True)
    print("[+] incoming/design cleaned and reset.")

if __name__ == "__main__":
    clean()