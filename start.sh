#!/bin/bash
# Kill any running agents
pkill -f "python agents/" 2>/dev/null && echo "Killed existing agents." || echo "No existing agents."
sleep 1

# Ensure logs directory exists
mkdir -p logs

# Activate venv
source venv/bin/activate

# Start all 6 agents, each with its own log file
python agents/scout.py      > logs/scout.log      2>&1 &  echo "Scout      PID $!"
python agents/forensics.py  > logs/forensics.log  2>&1 &  echo "Forensics  PID $!"
python agents/compliance.py > logs/compliance.log 2>&1 &  echo "Compliance PID $!"
python agents/gap.py        > logs/gap.log        2>&1 &  echo "Gap        PID $!"
python agents/risk.py       > logs/risk.log       2>&1 &  echo "Risk       PID $!"
python agents/synthesis.py  > logs/synthesis.log  2>&1 &  echo "Synthesis  PID $!"

echo ""
echo "All agents started. Watch logs with:"
echo "  tail -f logs/risk.log"
echo "  tail -f logs/synthesis.log"
