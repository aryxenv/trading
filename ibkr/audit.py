"""Executive report writing for research and council decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re


@dataclass(frozen=True)
class ExecutiveDecisionRecord:
    target: str
    thesis: str
    evidence: str
    council_decision: str
    confidence: str
    dissent: str
    proposed_action: str
    confirmation_status: str
    horizon_analysis: str = ""


def report_path(target: str, current_date: date | None = None, reports_dir: Path | str = "reports") -> Path:
    day = current_date or date.today()
    return Path(reports_dir) / f"{day:%Y%m%d}-{_slug(target)}.md"


def report_path_with_run_id(
    target: str,
    run_id: str,
    current_date: date | None = None,
    reports_dir: Path | str = "reports",
) -> Path:
    day = current_date or date.today()
    return Path(reports_dir) / f"{day:%Y%m%d}-{_slug(target)}-{_slug(run_id)}.md"


def write_executive_report(
    record: ExecutiveDecisionRecord,
    reports_dir: Path | str = "reports",
    current_date: date | None = None,
    run_id: str | None = None,
) -> Path:
    path = report_path(record.target, current_date=current_date, reports_dir=reports_dir)
    if path.exists():
        if not run_id:
            raise FileExistsError(f"Report already exists: {path}")
        path = report_path_with_run_id(record.target, run_id, current_date=current_date, reports_dir=reports_dir)
        if path.exists():
            raise FileExistsError(f"Report already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(record), encoding="utf-8")
    return path


def _render(record: ExecutiveDecisionRecord) -> str:
    return "\n".join(
        [
            f"# {record.target}",
            "",
            f"**Thesis:** {record.thesis}",
            "",
            f"**Horizon analysis:** {record.horizon_analysis or 'Not provided'}",
            "",
            f"**Evidence:** {record.evidence}",
            "",
            f"**Council decision:** {record.council_decision}",
            "",
            f"**Confidence:** {record.confidence}",
            "",
            f"**Dissent:** {record.dissent}",
            "",
            f"**Proposed action:** {record.proposed_action}",
            "",
            f"**Confirmation:** {record.confirmation_status}",
            "",
        ]
    )


def _slug(target: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", target.strip()).strip("-._").lower()
    if not slug:
        raise ValueError("Report target is required.")
    return slug
