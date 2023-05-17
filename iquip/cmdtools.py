import subprocess

def run_command(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)
