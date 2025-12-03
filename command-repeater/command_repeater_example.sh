#!/bin/bash
# Example demonstrating command_repeater.py usage

# This example simulates a scenario where:
# 1. We start a process with increasing load parameter
# 2. We wait for the process to complete (check string disappears from ps output)
# 3. We increment the load and repeat

echo "Example 1: Dry run to see what would execute"
echo "=============================================="
python3 command_repeater.py \
    --cmd1 "echo 'Starting process with load: {value}'" \
    --cmd2 "ps aux | grep python" \
    --check-string "nonexistent_process" \
    --start 50 \
    --max 150 \
    --increment 50 \
    --interval 2 \
    --dry-run

echo ""
echo ""
echo "Example 2: Real execution with echo commands"
echo "=============================================="
# This will actually execute but with harmless commands
python3 command_repeater.py \
    --cmd1 "echo 'Load level: {value}' && sleep 2" \
    --cmd2 "echo 'checking status' && date" \
    --check-string "nonexistent" \
    --start 100 \
    --max 200 \
    --increment 50 \
    --interval 1

echo ""
echo ""
echo "Example 3: Simulating a realistic scenario"
echo "==========================================="
echo "This would run:"
echo "  cmd1: curl -X POST http://api/load-test --data '{\"users\": {value}}'"
echo "  cmd2: curl http://api/status | grep 'status'"
echo "  check-string: 'running'"
echo ""
echo "Run with:"
cat << 'EOF'
python3 command_repeater.py \
    --cmd1 'curl -X POST http://localhost:8080/load-test --data "{\"users\": {value}}"' \
    --cmd2 'curl http://localhost:8080/status' \
    --check-string 'running' \
    --start 50 \
    --max 700 \
    --increment 50 \
    --interval 5 \
    --max-poll-attempts 60
EOF
