# Command Repeater Script

A Python script that executes commands repeatedly with incrementing parameters, polling for status between executions.

## Overview

This script automates the following workflow:
1. Execute a command with a numeric parameter
2. Poll a second command every N seconds until a specific string is no longer present in its output
3. Increment the parameter by a specified amount
4. Repeat until the parameter reaches a maximum value

## Use Cases

- **Load testing**: Gradually increase load on a system and wait for it to stabilize between increments
- **Batch processing**: Process data in chunks, waiting for each chunk to complete before starting the next
- **Service scaling**: Gradually scale up services and verify health between scale operations
- **Performance testing**: Test system behavior at different parameter values

## Installation

```bash
# The script is standalone and only requires Python 3.7+
chmod +x command_repeater.py
```

## Usage

### Basic Syntax

```bash
python3 command_repeater.py \
    --cmd1 "command_to_run {value}" \
    --cmd2 "status_check_command" \
    --check-string "string_to_wait_for_absence" \
    --start 50 \
    --max 700 \
    --increment 50
```

### Arguments

- `--cmd1`: First command to execute. Use `{value}` as placeholder for the parameter (REQUIRED)
- `--cmd2`: Second command to poll for status (REQUIRED)
- `--check-string`: String to check for in cmd2 output; script waits until it's absent (REQUIRED)
- `--start`: Starting parameter value (default: 50)
- `--max`: Maximum parameter value (default: 700)
- `--increment`: Amount to increment parameter each iteration (default: 50)
- `--interval`: Polling interval in seconds (default: 5)
- `--max-poll-attempts`: Maximum polling attempts before timing out (default: unlimited)
- `--dry-run`: Preview what would be executed without actually running commands

## Examples

### Example 1: Load Testing

Start a load test with increasing user count, waiting for system to stabilize:

```bash
python3 command_repeater.py \
    --cmd1 'curl -X POST http://api/load-test --data "{\"users\": {value}}"' \
    --cmd2 'curl http://api/status' \
    --check-string 'processing' \
    --start 50 \
    --max 700 \
    --increment 50 \
    --interval 5
```

### Example 2: Service Scaling

Scale up Kubernetes pods and wait for them to be ready:

```bash
python3 command_repeater.py \
    --cmd1 'kubectl scale deployment myapp --replicas={value}' \
    --cmd2 'kubectl get pods | grep myapp' \
    --check-string 'Pending' \
    --start 10 \
    --max 100 \
    --increment 10 \
    --interval 10
```

### Example 3: Batch Processing

Process data in increasing batch sizes:

```bash
python3 command_repeater.py \
    --cmd1 './process_data.sh --batch-size {value}' \
    --cmd2 'ps aux | grep process_data' \
    --check-string 'process_data.sh' \
    --start 100 \
    --max 1000 \
    --increment 100 \
    --interval 5 \
    --max-poll-attempts 60
```

### Example 4: Database Load Test

Test database with increasing connection count:

```bash
python3 command_repeater.py \
    --cmd1 'pgbench -c {value} -t 1000 mydb' \
    --cmd2 'pg_stat_activity | grep pgbench | wc -l' \
    --check-string '1' \
    --start 10 \
    --max 200 \
    --increment 10 \
    --interval 5
```

### Example 5: Dry Run

Preview what would be executed:

```bash
python3 command_repeater.py \
    --cmd1 'risky_command --param {value}' \
    --cmd2 'check_status' \
    --check-string 'running' \
    --start 50 \
    --max 700 \
    --increment 50 \
    --dry-run
```

## How It Works

1. **Initialization**: Parse arguments and validate parameters
2. **Main Loop**: For each parameter value from start to max:
   - Execute `cmd1` with current parameter value
   - Start polling loop:
     - Execute `cmd2`
     - Check if `check-string` is in output
     - If present, wait `interval` seconds and repeat
     - If absent, proceed to next iteration
   - Increment parameter by `increment`
3. **Completion**: Exit when parameter exceeds max value

## Output

The script provides detailed output:
- Iteration number and current parameter value
- Command execution status
- Polling progress and attempts
- Success/failure indicators
- Final summary

Example output:
```
======================================================================
Command Repeater Starting
======================================================================
Command 1: process_data.sh {value}
Command 2: ps aux | grep process_data
Check string: 'process_data.sh'
Parameter range: 50 to 700 (increment: 50)
Polling interval: 5s
======================================================================

[Iteration 1] Parameter value: 50
----------------------------------------------------------------------
Executing: process_data.sh 50
✓ Command executed successfully

  Polling command: ps aux | grep process_data
  Waiting for 'process_data.sh' to be absent from output...
  Attempt 1: String still present, waiting 5s...
  Attempt 2: String still present, waiting 5s...
  Attempt 3: String no longer present (attempt 3)
✓ Condition met, proceeding to next iteration

Next parameter value will be: 100
...
```

## Error Handling

- Command failures prompt for user confirmation to continue
- Polling timeout (if max-poll-attempts set) prompts for continuation
- Ctrl+C cleanly exits with appropriate status code
- Command timeouts (30s default) are handled gracefully

## Requirements

- Python 3.7+
- Standard library only (no external dependencies)
- Works on Linux, macOS, and Windows (with appropriate commands)

## Tips

1. **Test with dry-run first**: Always use `--dry-run` to verify your commands before actual execution
2. **Set reasonable intervals**: Too short may waste resources, too long delays progress
3. **Use max-poll-attempts**: Prevents infinite loops if the condition is never met
4. **Quote your commands**: Use single quotes to prevent shell expansion issues
5. **Log output**: Redirect output to file for later analysis: `python3 command_repeater.py ... > output.log 2>&1`

## Troubleshooting

### Command not found
Ensure your commands are in PATH or use absolute paths.

### {value} not replaced
Make sure to use single quotes around cmd1 to prevent shell expansion.

### Polling never completes
- Verify cmd2 actually shows the check-string initially
- Use `--max-poll-attempts` to prevent infinite loops
- Test cmd2 manually to ensure it works as expected

### Permission denied
Make sure the script is executable: `chmod +x command_repeater.py`

## License

This script is part of the tools repository and follows the same license.
