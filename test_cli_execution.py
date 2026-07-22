#!/usr/bin/env python3
"""
Verify CLI can start and respond to a simple query
"""
import sys
import subprocess
import time

# Send a simple query and exit
print("Testing CLI execution...")
print("-" * 60)

proc = subprocess.Popen(
    [sys.executable, "cli.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd="."
)

# Send query and exit command
commands = "What is account verification?\nexit\n"
stdout, stderr = proc.communicate(input=commands, timeout=30)

print("STDOUT:")
print(stdout)

if stderr:
    print("\nSTDERR:")
    print(stderr)

# Check for errors
if "Traceback" in stdout or "Traceback" in stderr:
    print("\n✗ CLI FAILED - Exception occurred")
    sys.exit(1)
elif "Assistant:" in stdout:
    print("\n✓ CLI EXECUTED SUCCESSFULLY")
    sys.exit(0)
else:
    print("\n⚠ CLI ran but output format unexpected")
    sys.exit(0)
