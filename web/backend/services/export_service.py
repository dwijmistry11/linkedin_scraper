"""Export scrape results as JSON or CSV."""

import csv
import io
import json
from typing import Any


def result_to_json(result_data: str) -> str:
    """Pretty-print the stored JSON result."""
    parsed = json.loads(result_data)
    return json.dumps(parsed, indent=2)


def result_to_csv(scrape_type: str, result_data: str) -> str:
    """Flatten a scrape result into CSV."""
    parsed = json.loads(result_data)

    # Normalize to list of dicts
    if isinstance(parsed, dict):
        rows = [parsed]
    elif isinstance(parsed, list):
        if parsed and isinstance(parsed[0], str):
            # job_search returns list of URL strings
            rows = [{"url": u} for u in parsed]
        else:
            rows = parsed
    else:
        rows = [{"value": parsed}]

    if not rows:
        return ""

    # Flatten nested dicts/lists to JSON strings for CSV compatibility
    flat_rows: list[dict[str, Any]] = []
    for row in rows:
        flat: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, (dict, list)):
                flat[k] = json.dumps(v)
            else:
                flat[k] = v
        flat_rows.append(flat)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=flat_rows[0].keys())
    writer.writeheader()
    writer.writerows(flat_rows)
    return output.getvalue()
