from __future__ import annotations

import json
import os
from typing import Dict


SUMMARY_FILE = "community_summaries.json"


def save_summaries(path: str, summaries: Dict[int, Dict]) -> str:
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, SUMMARY_FILE)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in summaries.items()}, f, indent=2)
    return file_path


def load_summaries(path: str) -> Dict[int, Dict]:
    file_path = os.path.join(path, SUMMARY_FILE)
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return {int(k): v for k, v in payload.items()}
