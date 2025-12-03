#!/usr/bin/env python3
"""
Command Repeater Script

This script:
1. Runs a command with a parameter value
2. Polls a second command every 5 seconds until a specific string is no longer present in output
3. Increments the parameter by 50 and repeats
4. Stops when parameter reaches the maximum value (700)

Usage:
    python command_repeater.py --cmd1 "command {value}" --cmd2 "status_command" \\
                               --check-string "Processing" --start 50 --max 700 --increment 50
"""

import argparse
import subprocess
import time
import sys
from typing import Optional


def run_command(command: str, shell: bool = True) -> tuple[int, str, str]:
    """
    Execute a shell command and return the result.
    
    Args:
        command: Command to execute
        shell: Whether to run command through shell
        
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print(f"Command timed out: {command}", file=sys.stderr)
        return -1, "", "Command timed out"
    except Exception as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        return -1, "", str(e)


def poll_until_string_absent(
    command: str,
    check_string: str,
    interval: int = 5,
    max_attempts: Optional[int] = None
) -> bool:
    """
    Poll a command until a specific string is no longer present in output.
    
    Args:
        command: Command to poll
        check_string: String to check for absence
        interval: Polling interval in seconds
        max_attempts: Maximum polling attempts (None for unlimited)
        
    Returns:
        True if string became absent, False if max_attempts reached
    """
    attempts = 0
    print(f"  Polling command: {command}")
    print(f"  Waiting for '{check_string}' to be absent from output...")
    
    while True:
        attempts += 1
        if max_attempts and attempts > max_attempts:
            print(f"  Max attempts ({max_attempts}) reached")
            return False
        
        returncode, stdout, stderr = run_command(command)
        
        if returncode != 0:
            print(f"  Warning: Poll command returned {returncode}", file=sys.stderr)
        
        # Check if string is present in output
        output = stdout + stderr
        if check_string not in output:
            print(f"  String '{check_string}' no longer present (attempt {attempts})")
            return True
        
        print(f"  Attempt {attempts}: String still present, waiting {interval}s...")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description="Run command repeatedly with incrementing parameter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python command_repeater.py \\
      --cmd1 "process_data.sh {value}" \\
      --cmd2 "check_status.sh" \\
      --check-string "Processing" \\
      --start 50 --max 700 --increment 50

  # With custom interval
  python command_repeater.py \\
      --cmd1 "load_test --users {value}" \\
      --cmd2 "ps aux | grep load_test" \\
      --check-string "load_test" \\
      --start 100 --max 500 --increment 100 \\
      --interval 10

  # With max polling attempts
  python command_repeater.py \\
      --cmd1 "start_service --threads {value}" \\
      --cmd2 "systemctl status myservice" \\
      --check-string "starting" \\
      --start 50 --max 700 --increment 50 \\
      --max-poll-attempts 60
        """
    )
    
    parser.add_argument(
        "--cmd1",
        required=True,
        help="First command to execute. Use {value} as placeholder for parameter"
    )
    parser.add_argument(
        "--cmd2",
        required=True,
        help="Second command to poll for status"
    )
    parser.add_argument(
        "--check-string",
        required=True,
        help="String to wait for absence in cmd2 output"
    )
    parser.add_argument(
        "--start",
        type=int,
        default=50,
        help="Starting parameter value (default: 50)"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=700,
        help="Maximum parameter value (default: 700)"
    )
    parser.add_argument(
        "--increment",
        type=int,
        default=50,
        help="Parameter increment value (default: 50)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Polling interval in seconds (default: 5)"
    )
    parser.add_argument(
        "--max-poll-attempts",
        type=int,
        help="Maximum polling attempts before giving up (default: unlimited)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if "{value}" not in args.cmd1:
        print("Error: --cmd1 must contain {value} placeholder", file=sys.stderr)
        sys.exit(1)
    
    if args.start > args.max:
        print("Error: --start must be <= --max", file=sys.stderr)
        sys.exit(1)
    
    if args.increment <= 0:
        print("Error: --increment must be positive", file=sys.stderr)
        sys.exit(1)
    
    print("=" * 70)
    print("Command Repeater Starting")
    print("=" * 70)
    print(f"Command 1: {args.cmd1}")
    print(f"Command 2: {args.cmd2}")
    print(f"Check string: '{args.check_string}'")
    print(f"Parameter range: {args.start} to {args.max} (increment: {args.increment})")
    print(f"Polling interval: {args.interval}s")
    if args.max_poll_attempts:
        print(f"Max poll attempts: {args.max_poll_attempts}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 70)
    print()
    
    current_value = args.start
    iteration = 1
    
    while current_value <= args.max:
        print(f"\n[Iteration {iteration}] Parameter value: {current_value}")
        print("-" * 70)
        
        # Step 1: Execute first command with current parameter value
        cmd1_with_value = args.cmd1.format(value=current_value)
        print(f"Executing: {cmd1_with_value}")
        
        if not args.dry_run:
            returncode, stdout, stderr = run_command(cmd1_with_value)
            
            if returncode == 0:
                print(f"✓ Command executed successfully")
                if stdout.strip():
                    print(f"  Output: {stdout.strip()[:200]}")  # First 200 chars
            else:
                print(f"✗ Command failed with return code {returncode}", file=sys.stderr)
                if stderr.strip():
                    print(f"  Error: {stderr.strip()[:200]}", file=sys.stderr)
                
                # Decide whether to continue or abort
                response = input("  Continue anyway? (y/n): ").strip().lower()
                if response != 'y':
                    print("Aborted by user")
                    sys.exit(1)
        else:
            print("  [DRY RUN] Would execute command")
        
        # Step 2: Poll second command until check string is absent
        print()
        if not args.dry_run:
            success = poll_until_string_absent(
                args.cmd2,
                args.check_string,
                args.interval,
                args.max_poll_attempts
            )
            
            if not success:
                print("✗ Polling timed out or max attempts reached", file=sys.stderr)
                response = input("  Continue to next iteration? (y/n): ").strip().lower()
                if response != 'y':
                    print("Aborted by user")
                    sys.exit(1)
            else:
                print("✓ Condition met, proceeding to next iteration")
        else:
            print("  [DRY RUN] Would poll command until string absent")
        
        # Step 3: Increment parameter value
        current_value += args.increment
        iteration += 1
        
        if current_value <= args.max:
            print(f"\nNext parameter value will be: {current_value}")
        else:
            print(f"\nParameter value {current_value} exceeds maximum {args.max}")
    
    print()
    print("=" * 70)
    print("Command Repeater Completed")
    print(f"Total iterations: {iteration - 1}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        sys.exit(1)
