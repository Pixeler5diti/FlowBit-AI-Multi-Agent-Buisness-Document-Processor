import json
import os
from datetime import datetime

RUNS_FILE = 'data/runs.json'

def load_runs():
    if os.path.exists(RUNS_FILE):
        with open(RUNS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_run(run_id, input_data, summary=None):
    runs = load_runs()

    runs[run_id] = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "input": input_data,
        "summary": summary
    }

    with open(RUNS_FILE, 'w') as f:
        json.dump(runs, f, indent=2)
