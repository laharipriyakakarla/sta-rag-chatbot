"""
chunker.py
Parses OpenROAD timing reports into per-path chunks with metadata.
Each chunk = one timing path (Startpoint → slack line).
"""

import re
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimingPath:
    startpoint: str
    endpoint: str
    path_group: str
    path_type: str          # min or max
    slack: float
    slack_status: str       # MET or VIOLATED
    stage: str              # which report file (e.g. 6_finish)
    raw_text: str           # full path text for embedding
    data_arrival_time: Optional[float] = None
    data_required_time: Optional[float] = None


def parse_stage_name(filepath: str) -> str:
    """Extract stage name from filename e.g. '6_finish' from '6_finish.rpt'"""
    basename = os.path.basename(filepath)
    return basename.replace(".rpt", "")


def parse_report(filepath: str) -> list[TimingPath]:
    """Parse a single .rpt file and return list of TimingPath objects."""
    stage = parse_stage_name(filepath)

    with open(filepath, "r") as f:
        content = f.read()

    # Split on "Startpoint:" to get individual path blocks
    # First element is usually header/summary before first path
    raw_blocks = re.split(r"(?=^Startpoint:)", content, flags=re.MULTILINE)

    paths = []
    for block in raw_blocks:
        block = block.strip()
        if not block.startswith("Startpoint:"):
            continue

        path = extract_path(block, stage)
        if path:
            paths.append(path)

    return paths


def extract_path(block: str, stage: str) -> Optional[TimingPath]:
    """Extract structured data from a single path block."""
    lines = block.splitlines()

    startpoint = None
    endpoint = None
    path_group = None
    path_type = None
    slack = None
    slack_status = None
    data_arrival_time = None
    data_required_time = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Startpoint (may span 2 lines)
        if line.startswith("Startpoint:"):
            startpoint = line.replace("Startpoint:", "").strip()
            # check if next line is continuation (indented, no keyword)
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not any(next_line.startswith(k) for k in
                        ["Endpoint:", "Path Group:", "Path Type:", "Fanout", "---"]):
                    startpoint += " " + next_line
                    i += 1

        # Endpoint (may span 2 lines)
        elif line.startswith("Endpoint:"):
            endpoint = line.replace("Endpoint:", "").strip()
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not any(next_line.startswith(k) for k in
                        ["Path Group:", "Path Type:", "Fanout", "---"]):
                    endpoint += " " + next_line
                    i += 1

        elif line.startswith("Path Group:"):
            path_group = line.replace("Path Group:", "").strip()

        elif line.startswith("Path Type:"):
            path_type = line.replace("Path Type:", "").strip()

        elif "data arrival time" in line:
            parts = line.split()
            # value is always the last number on the line
            for part in reversed(parts):
                try:
                    data_arrival_time = float(part)
                    break
                except ValueError:
                    continue

        elif "data required time" in line and "library" not in line:
            parts = line.split()
            for part in reversed(parts):
                try:
                    data_required_time = float(part)
                    break
                except ValueError:
                    continue

        elif "slack (MET)" in line or "slack (VIOLATED)" in line:
            # OpenROAD format: "   63.96   slack (MET)" — value is BEFORE the keyword
            match = re.search(r"([-\d.]+)\s+slack\s+\((MET|VIOLATED)\)", line)
            if match:
                slack = float(match.group(1))
                slack_status = match.group(2)

        i += 1

    # Only return if we got the essential fields
    if all(v is not None for v in [startpoint, endpoint, path_group, path_type, slack, slack_status]):
        return TimingPath(
            startpoint=startpoint,
            endpoint=endpoint,
            path_group=path_group,
            path_type=path_type,
            slack=slack,
            slack_status=slack_status,
            stage=stage,
            raw_text=block,
            data_arrival_time=data_arrival_time,
            data_required_time=data_required_time,
        )
    return None


def parse_all_reports(reports_dir: str) -> list[TimingPath]:
    """Parse all .rpt files in a directory."""
    rpt_files = sorted([
        os.path.join(reports_dir, f)
        for f in os.listdir(reports_dir)
        if f.endswith(".rpt")
    ])

    all_paths = []
    for rpt_file in rpt_files:
        paths = parse_report(rpt_file)
        print(f"  {os.path.basename(rpt_file)}: {len(paths)} paths parsed")
        all_paths.extend(paths)

    return all_paths


def summarize(paths: list[TimingPath]):
    """Print a quick summary of parsed paths."""
    print(f"\nTotal paths: {len(paths)}")
    print(f"  MET:      {sum(1 for p in paths if p.slack_status == 'MET')}")
    print(f"  VIOLATED: {sum(1 for p in paths if p.slack_status == 'VIOLATED')}")
    print(f"\nPath groups: {set(p.path_group for p in paths)}")
    print(f"Path types:  {set(p.path_type for p in paths)}")
    print(f"Stages:      {set(p.stage for p in paths)}")

    worst = min(paths, key=lambda p: p.slack)
    best  = max(paths, key=lambda p: p.slack)
    print(f"\nWorst slack: {worst.slack} ({worst.slack_status}) — {worst.startpoint[:60]}")
    print(f"Best slack:  {best.slack}  ({best.slack_status}) — {best.startpoint[:60]}")


if __name__ == "__main__":
    import sys
    reports_dir = sys.argv[1] if len(sys.argv) > 1 else "./reports"
    print(f"Parsing reports in: {reports_dir}\n")
    paths = parse_all_reports(reports_dir)
    summarize(paths)
