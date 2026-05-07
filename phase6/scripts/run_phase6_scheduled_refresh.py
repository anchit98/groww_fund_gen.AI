import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 6 scheduled refresh + operations checks")
    parser.add_argument("--update-baseline", action="store_true", help="Update phase6 drift baseline after checks")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    py = sys.executable

    refresh_cmd = [py, "phase1_5/scripts/run_refresh_pipeline.py"]
    refresh = subprocess.run(refresh_cmd, cwd=str(repo_root), check=False)
    if refresh.returncode != 0:
        raise SystemExit(refresh.returncode)

    ops_cmd = [
        py,
        "phase6/scripts/run_phase6_operations.py",
        "--policy",
        "phase6/policy/operations_policy.json",
        "--status-out",
        "phase6/reports/ops_status.json",
        "--summary-out",
        "phase6/reports/ops_summary.md",
        "--change-log-out",
        "phase6/reports/source_change_log.md",
    ]
    if args.update_baseline:
        ops_cmd.append("--update-baseline")

    checks = subprocess.run(ops_cmd, cwd=str(repo_root), check=False)
    raise SystemExit(checks.returncode)


if __name__ == "__main__":
    main()
