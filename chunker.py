"""
chunker.py
Parses OpenROAD and PrimeTime timing reports into per-path chunks with metadata.
Auto-detects report format per file.
Each chunk = one timing path (Startpoint → slack line).
"""

import re
import os
from dataclasses import dataclass
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
    tool: str               # 'openroad' or 'primetime'
    raw_text: str           # full path text for embedding
    data_arrival_time: Optional[float] = None
    data_required_time: Optional[float] = None


# ── Format detection ────────────────────────────────────────────────────────────

def detect_format(content: str) -> str:
    """
    Detect whether the report is from OpenROAD or PrimeTime.
    PrimeTime uses 'Point ... Incr ... Path' column header.
    OpenROAD uses 'Delay ... Time ... Description' column header.
    """
    if re.search(r"^\s+Point\s+.*Incr\s+.*Path", content, re.MULTILINE):
        return "primetime"
    return "openroad"


# ── Stage name ──────────────────────────────────────────────────────────────────

def parse_stage_name(filepath: str) -> str:
    basename = os.path.basename(filepath)
    for ext in (".rpt", ".txt", ".log"):
        basename = basename.replace(ext, "")
    return basename


# ── Shared header parser (same for both tools) ──────────────────────────────────

def parse_header(lines: list[str]) -> dict:
    """Parse Startpoint/Endpoint/Path Group/Path Type — identical in both tools."""
    result = {
        "startpoint": None,
        "endpoint": None,
        "path_group": None,
        "path_type": None,
    }
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("Startpoint:"):
            val = line.replace("Startpoint:", "").strip()
            if i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if nxt and not any(nxt.startswith(k) for k in
                        ["Endpoint:", "Path Group:", "Path Type:", "Fanout",
                         "Point", "---", "Cap", "Delay"]):
                    val += " " + nxt
                    i += 1
            result["startpoint"] = val

        elif line.startswith("Endpoint:"):
            val = line.replace("Endpoint:", "").strip()
            if i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if nxt and not any(nxt.startswith(k) for k in
                        ["Path Group:", "Path Type:", "Fanout",
                         "Point", "---", "Cap", "Delay"]):
                    val += " " + nxt
                    i += 1
            result["endpoint"] = val

        elif line.startswith("Path Group:"):
            result["path_group"] = line.replace("Path Group:", "").strip()

        elif line.startswith("Path Type:"):
            result["path_type"] = line.replace("Path Type:", "").strip()

        i += 1
    return result


# ── OpenROAD parser ─────────────────────────────────────────────────────────────

def extract_path_openroad(block: str, stage: str) -> Optional[TimingPath]:
    """Parse a single path block from an OpenROAD report."""
    lines = block.splitlines()
    header = parse_header(lines)

    slack = None
    slack_status = None
    data_arrival_time = None
    data_required_time = None

    for line in lines:
        stripped = line.strip()

        if "slack (MET)" in stripped or "slack (VIOLATED)" in stripped:
            # OpenROAD: "   63.96   slack (MET)"  — value BEFORE keyword
            match = re.search(r"([-\d.]+)\s+slack\s+\((MET|VIOLATED)\)", stripped)
            if match:
                slack = float(match.group(1))
                slack_status = match.group(2)

        elif "data arrival time" in stripped:
            parts = stripped.split()
            for part in reversed(parts):
                try:
                    data_arrival_time = float(part)
                    break
                except ValueError:
                    continue

        elif "data required time" in stripped and "library" not in stripped:
            parts = stripped.split()
            for part in reversed(parts):
                try:
                    data_required_time = float(part)
                    break
                except ValueError:
                    continue

    if all(v is not None for v in [
        header["startpoint"], header["endpoint"],
        header["path_group"], header["path_type"],
        slack, slack_status
    ]):
        return TimingPath(
            startpoint=header["startpoint"],
            endpoint=header["endpoint"],
            path_group=header["path_group"],
            path_type=header["path_type"],
            slack=slack,
            slack_status=slack_status,
            stage=stage,
            tool="openroad",
            raw_text=block,
            data_arrival_time=data_arrival_time,
            data_required_time=data_required_time,
        )
    return None


# ── PrimeTime parser ────────────────────────────────────────────────────────────

def extract_path_primetime(block: str, stage: str) -> Optional[TimingPath]:
    """
    Parse a single path block from a PrimeTime report.

    PrimeTime slack line format:
        slack (MET)                          1.31
        slack (VIOLATED)                    -0.45
    Value is AFTER the keyword (opposite of OpenROAD).
    """
    lines = block.splitlines()
    header = parse_header(lines)

    slack = None
    slack_status = None
    data_arrival_time = None
    data_required_time = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("slack (MET)") or stripped.startswith("slack (VIOLATED)"):
            # PrimeTime: "slack (MET)    1.31" — value AFTER keyword
            match = re.search(r"slack\s+\((MET|VIOLATED)\)\s+([-\d.]+)", stripped)
            if match:
                slack_status = match.group(1)
                slack = float(match.group(2))

        elif stripped.startswith("data arrival time"):
            parts = stripped.split()
            for part in reversed(parts):
                try:
                    data_arrival_time = float(part)
                    break
                except ValueError:
                    continue

        elif stripped.startswith("data required time") and "library" not in stripped:
            parts = stripped.split()
            for part in reversed(parts):
                try:
                    data_required_time = float(part)
                    break
                except ValueError:
                    continue

    if all(v is not None for v in [
        header["startpoint"], header["endpoint"],
        header["path_group"], header["path_type"],
        slack, slack_status
    ]):
        return TimingPath(
            startpoint=header["startpoint"],
            endpoint=header["endpoint"],
            path_group=header["path_group"],
            path_type=header["path_type"],
            slack=slack,
            slack_status=slack_status,
            stage=stage,
            tool="primetime",
            raw_text=block,
            data_arrival_time=data_arrival_time,
            data_required_time=data_required_time,
        )
    return None


# ── Main parse functions ────────────────────────────────────────────────────────

def parse_report(filepath: str) -> list[TimingPath]:
    """Parse a single report file — auto-detects OpenROAD vs PrimeTime."""
    stage = parse_stage_name(filepath)

    with open(filepath, "r") as f:
        content = f.read()

    fmt = detect_format(content)
    extractor = extract_path_primetime if fmt == "primetime" else extract_path_openroad

    raw_blocks = re.split(r"(?=^Startpoint:)", content, flags=re.MULTILINE)

    paths = []
    for block in raw_blocks:
        block = block.strip()
        if not block.startswith("Startpoint:"):
            continue
        path = extractor(block, stage)
        if path:
            paths.append(path)

    return paths


def parse_all_reports(reports_dir: str) -> list[TimingPath]:
    """Parse all .rpt/.txt/.log files in a directory."""
    extensions = (".rpt", ".txt", ".log")
    report_files = sorted([
        os.path.join(reports_dir, f)
        for f in os.listdir(reports_dir)
        if f.endswith(extensions)
    ])

    all_paths = []
    for rpt_file in report_files:
        with open(rpt_file, "r") as f:
            content = f.read()
        fmt = detect_format(content)
        paths = parse_report(rpt_file)
        print(f"  {os.path.basename(rpt_file)}: {len(paths)} paths parsed [{fmt}]")
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
    print(f"Tools:       {set(p.tool for p in paths)}")

    worst = min(paths, key=lambda p: p.slack)
    best  = max(paths, key=lambda p: p.slack)
    print(f"\nWorst slack: {worst.slack} ({worst.slack_status}) [{worst.tool}] — {worst.startpoint[:60]}")
    print(f"Best slack:  {best.slack}  ({best.slack_status}) [{best.tool}] — {best.startpoint[:60]}")


if __name__ == "__main__":
    import sys
    reports_dir = sys.argv[1] if len(sys.argv) > 1 else "./reports"
    print(f"Parsing reports in: {reports_dir}\n")
    paths = parse_all_reports(reports_dir)
    summarize(paths)
