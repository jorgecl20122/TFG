import json
import os
from datetime import datetime

LOG_FOLDER = "data/logs"
LOG_FILE = os.path.join(LOG_FOLDER, "app_logs.jsonl")


def write_log(module, action, user=None, job_id=None, shortcut=None, details=None):
    os.makedirs(LOG_FOLDER, exist_ok=True)

    log_entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "module": module,
        "action": action,
        "user": user,
        "job_id": job_id,
        "shortcut": shortcut,
        "details": details or {}
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")