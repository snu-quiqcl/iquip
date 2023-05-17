"""Utility module for handling the command line."""

import subprocess

def run_command(cmd):
    """Runs the command line and returns the result.

    If the command line is completed without any error,
    the printed result would be stored in the 'stdout' field of the return value.
    Otherwise, the printed error would be stored in the 'stderr' field.

    Args:
        cmd: The string of the command line to run.
    """
    return subprocess.run(cmd, capture_output=True, shell=True, check=True, text=True)
