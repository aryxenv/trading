"""Validation helpers for agentic research and council artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ibkr.serialization import read_json

HORIZONS = ("short_term_1_3m", "medium_term_3_12m", "long_term_1y_plus")

_REQUIRED_PACKET_ARTIFACTS = (
    "symbol_resolution",
    "portfolio_snapshot",
    "position_context",
    "target_context",
    "ibkr_news",
)

_AGENT_CLAIM_TERMS = (
    "agent-reported",
    "agent reported",
    "agent-referenced",
    "agent referenced",
    "agent summary",
    "agent output",
    "route reported",
)

_SOURCE_ANCHORS = (
    "http://",
    "https://",
    ".json",
    ".md",
    "sandbox\\",
    "sandbox/",
    "ibkr",
    "sec",
    "edgar",
)

_REPORT_PATH_MARKERS = ("reports\\", "reports/")


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        data = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.path:
            data["path"] = self.path
        return data


def validate_research_packet(packet_path: Path | str, *, base_dir: Path | str | None = None) -> list[ValidationIssue]:
    """Validate a research packet and its route artifacts."""

    packet_file = _input_file(packet_path, "research-packet.json")
    root = Path(base_dir or Path.cwd()).resolve()
    packet = _read_mapping(packet_file)
    issues: list[ValidationIssue] = []

    if packet.get("schema_version") != "ibkr.research_packet.v1":
        issues.append(_error("packet.schema", "Research packet schema_version must be ibkr.research_packet.v1."))

    run_id = _text(packet.get("run_id"))
    target_symbol = _target_symbol(packet.get("target"))
    artifact_paths = _mapping(packet.get("artifact_paths"))
    for key in _REQUIRED_PACKET_ARTIFACTS:
        _require_artifact_file(issues, artifact_paths, key, root)

    horizon_analysis = _mapping(packet.get("horizon_analysis"))
    for horizon in HORIZONS:
        if not _mapping(horizon_analysis.get(horizon)):
            issues.append(_error("packet.horizon_missing", f"Research packet missing horizon_analysis.{horizon}."))

    route_horizons_with_artifacts: set[str] = set()
    routes = packet.get("agent_routes")
    if not isinstance(routes, list) or not routes:
        issues.append(_error("packet.routes_missing", "Research packet must include non-empty agent_routes."))
    else:
        for index, route_value in enumerate(routes):
            route = _mapping(route_value)
            route_path = f"agent_routes[{index}]"
            name = _text(route.get("name")) or f"route-{index}"
            status = _text(route.get("status")).lower()
            if status and status != "completed":
                issues.append(_warning("route.not_completed", f"Route {name} status is {status!r}, not completed.", route_path))

            folder_value = route.get("folder")
            if not isinstance(folder_value, str) or not folder_value.strip():
                issues.append(_error("route.folder_missing", f"Route {name} missing folder.", route_path))
                continue

            folder = _resolve_artifact_path(folder_value, root)
            if not folder.is_dir():
                issues.append(_error("route.folder_missing", f"Route {name} folder does not exist: {folder}", route_path))
                continue

            findings_path = folder / "findings.json"
            if not _non_empty_file(findings_path):
                issues.append(
                    _error(
                        "route.findings_missing",
                        f"Route {name} must write non-empty findings.json: {findings_path}",
                        route_path,
                    )
                )
                continue

            findings = _read_mapping(findings_path)
            expected_horizon = _expected_horizon(name)
            if expected_horizon:
                route_horizons_with_artifacts.add(expected_horizon)
                actual_horizon = _text(findings.get("horizon"))
                if actual_horizon != expected_horizon:
                    issues.append(
                        _error(
                            "route.horizon_mismatch",
                            f"Route {name} findings horizon {actual_horizon!r} does not match {expected_horizon}.",
                            str(findings_path),
                        )
                    )

            if run_id and _text(findings.get("run_id")) != run_id:
                issues.append(
                    _error(
                        "route.run_id_mismatch",
                        f"Route {name} findings run_id does not match packet run_id {run_id}.",
                        str(findings_path),
                    )
                )

            findings_target = _target_symbol(findings.get("target")) or _text(findings.get("target"))
            if target_symbol and findings_target and findings_target.upper() != target_symbol.upper():
                issues.append(
                    _error(
                        "route.target_mismatch",
                        f"Route {name} findings target {findings_target!r} does not match packet target {target_symbol}.",
                        str(findings_path),
                    )
                )

            _require_non_empty_list(issues, findings, "sources", "route.sources_missing", str(findings_path), error=True)
            _require_non_empty_list(issues, findings, "facts", "route.facts_missing", str(findings_path), error=True)
            _require_non_empty_list(issues, findings, "stats", "route.stats_missing", str(findings_path), error=False)
            _require_non_empty_list(
                issues,
                findings,
                "contrarian_evidence",
                "route.contrarian_missing",
                str(findings_path),
                error=False,
            )
            _require_non_empty_list(
                issues,
                findings,
                "pruned_routes",
                "route.pruned_missing",
                str(findings_path),
                error=False,
            )

    for horizon in HORIZONS:
        if horizon not in route_horizons_with_artifacts:
            issues.append(
                _error(
                    "packet.horizon_route_missing",
                    f"No completed route findings artifact supports horizon {horizon}.",
                )
            )

    sourced_findings = packet.get("sourced_findings")
    if not isinstance(sourced_findings, list) or not sourced_findings:
        issues.append(_error("packet.sourced_findings_missing", "Research packet must include sourced_findings."))
    else:
        for index, finding_value in enumerate(sourced_findings):
            finding = _mapping(finding_value)
            finding_path = f"sourced_findings[{index}]"
            source = _text(finding.get("source"))
            if not source:
                issues.append(_error("finding.source_missing", "Sourced finding missing source.", finding_path))
            if _references_prior_report(source):
                issues.append(
                    _error(
                        "finding.prior_report_source",
                        "Prior reports under reports/ are audit logs, not research evidence sources.",
                        finding_path,
                    )
                )
            if not _text(finding.get("confidence")):
                issues.append(_warning("finding.confidence_missing", "Sourced finding missing confidence.", finding_path))
            text = f"{_text(finding.get('finding'))} {source}".lower()
            if _looks_like_unsupported_agent_claim(text):
                issues.append(
                    _warning(
                        "finding.unsupported_agent_claim",
                        "Agent-reported claim lacks durable artifact/source anchor.",
                        finding_path,
                    )
                )

    return issues


def validate_council_record(record_path: Path | str, *, base_dir: Path | str | None = None) -> list[ValidationIssue]:
    """Validate council record and member vote artifacts."""

    record_file = _input_file(record_path, "report-input.json")
    root = Path(base_dir or Path.cwd()).resolve()
    record = _read_mapping(record_file)
    issues: list[ValidationIssue] = []

    run_id = _text(record.get("run_id"))
    council_process = _mapping(record.get("council_process"))
    if not council_process:
        issues.append(_error("council.process_missing", "Council record missing council_process."))

    structured_horizons = _mapping(record.get("horizon_analysis_structured"))
    if not structured_horizons:
        issues.append(_warning("council.structured_horizons_missing", "Council record missing horizon_analysis_structured."))
    for horizon in HORIZONS:
        if structured_horizons and not _mapping(structured_horizons.get(horizon)):
            issues.append(_error("council.horizon_missing", f"Council record missing {horizon} structured analysis."))

    members = council_process.get("members")
    if not isinstance(members, list) or not members:
        issues.append(_error("council.members_missing", "Council process must list members."))
        members = []

    vote_summary = _mapping(council_process.get("vote_summary"))
    for horizon in (*HORIZONS, "overall"):
        if vote_summary and not _mapping(vote_summary.get(horizon)):
            issues.append(_warning("council.vote_summary_missing", f"Council vote_summary missing {horizon}."))

    for member_value in members:
        member = _text(member_value)
        if not member:
            continue
        folder = _council_member_folder(member, run_id, record_file, root)
        if not folder.is_dir():
            issues.append(_error("council.folder_missing", f"Council member folder does not exist: {folder}", member))
            continue

        vote_path = folder / "vote.json"
        critique_path = folder / "critique.json"
        if not _non_empty_file(vote_path):
            issues.append(_error("council.vote_missing", f"Council member must write non-empty vote.json: {vote_path}", member))
            continue
        if not _non_empty_file(critique_path):
            issues.append(
                _error("council.critique_missing", f"Council member must write non-empty critique.json: {critique_path}", member)
            )

        vote = _read_mapping(vote_path)
        if _text(vote.get("member")) and _text(vote.get("member")) != member:
            issues.append(_error("council.member_mismatch", f"vote.json member does not match {member}.", str(vote_path)))

        decisions = _mapping(vote.get("decisions") or vote.get("horizon_decisions"))
        for horizon in HORIZONS:
            decision = _mapping(decisions.get(horizon))
            if not decision:
                issues.append(_error("council.vote_horizon_missing", f"{member} vote missing {horizon}.", str(vote_path)))
                continue
            _require_non_empty_list(
                issues,
                decision,
                "evidence_ids",
                "council.evidence_ids_missing",
                f"{vote_path}:{horizon}",
                error=False,
            )
            _require_non_empty_list(
                issues,
                decision,
                "disconfirming_evidence",
                "council.disconfirming_missing",
                f"{vote_path}:{horizon}",
                error=False,
            )
            summary_vote = _summary_vote(vote_summary, horizon, member)
            vote_decision = _text(decision.get("decision"))
            if summary_vote and vote_decision and not _compatible_decisions(summary_vote, vote_decision):
                issues.append(
                    _warning(
                        "council.vote_summary_mismatch",
                        f"vote_summary has {summary_vote!r} for {member}/{horizon}, vote.json has {vote_decision!r}.",
                        str(vote_path),
                    )
                )

        overall = _mapping(vote.get("overall"))
        if not overall:
            issues.append(_warning("council.overall_missing", f"{member} vote missing overall section.", str(vote_path)))

    return issues


def validation_result(kind: str, input_path: Path | str, issues: list[ValidationIssue]) -> dict[str, Any]:
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    return {
        "schema_version": "ibkr.validation_result.v1",
        "kind": kind,
        "input": str(input_path),
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": [issue.to_dict() for issue in issues],
    }


def has_blocking_issues(issues: list[ValidationIssue], *, fail_on_warnings: bool = False) -> bool:
    return any(issue.severity == "error" or (fail_on_warnings and issue.severity == "warning") for issue in issues)


def _input_file(path: Path | str, default_name: str) -> Path:
    candidate = Path(path)
    if candidate.is_dir():
        return candidate / default_name
    return candidate


def _read_mapping(path: Path) -> dict[str, Any]:
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _resolve_artifact_path(path_value: str, root: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return root / path


def _require_artifact_file(issues: list[ValidationIssue], artifact_paths: dict[str, Any], key: str, root: Path) -> None:
    value = artifact_paths.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(_error("artifact.path_missing", f"artifact_paths.{key} is required.", f"artifact_paths.{key}"))
        return
    path = _resolve_artifact_path(value, root)
    if not _non_empty_file(path):
        issues.append(_error("artifact.file_missing", f"Required artifact missing or empty: {path}", f"artifact_paths.{key}"))


def _non_empty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _target_symbol(value: Any) -> str:
    if isinstance(value, dict):
        return _text(value.get("resolved_symbol") or value.get("symbol") or value.get("target"))
    return _text(value)


def _expected_horizon(route_name: str) -> str:
    lower = route_name.lower().replace("_", "-")
    if lower.startswith("short"):
        return "short_term_1_3m"
    if lower.startswith("medium"):
        return "medium_term_3_12m"
    if lower.startswith("long"):
        return "long_term_1y_plus"
    return ""


def _require_non_empty_list(
    issues: list[ValidationIssue],
    data: dict[str, Any],
    key: str,
    code: str,
    path: str,
    *,
    error: bool,
) -> None:
    value = data.get(key)
    if isinstance(value, list) and value:
        return
    issue = _error if error else _warning
    issues.append(issue(code, f"Missing non-empty {key}.", path))


def _looks_like_unsupported_agent_claim(text: str) -> bool:
    if not any(term in text for term in _AGENT_CLAIM_TERMS):
        return False
    return not any(anchor in text for anchor in _SOURCE_ANCHORS)


def _references_prior_report(value: str) -> bool:
    normalized = value.lower().replace("/", "\\")
    return any(marker.replace("/", "\\") in normalized for marker in _REPORT_PATH_MARKERS)


def _council_member_folder(member: str, run_id: str, record_file: Path, root: Path) -> Path:
    if run_id:
        return root / "sandbox" / run_id / member
    return record_file.parent / member


def _summary_vote(vote_summary: dict[str, Any], horizon: str, member: str) -> str:
    horizon_summary = _mapping(vote_summary.get(horizon))
    votes = _mapping(horizon_summary.get("votes"))
    return _text(votes.get(member))


def _compatible_decisions(left: str, right: str) -> bool:
    normalized_left = _normalize_decision(left)
    normalized_right = _normalize_decision(right)
    return (
        normalized_left == normalized_right
        or normalized_left in normalized_right
        or normalized_right in normalized_left
    )


def _normalize_decision(value: str) -> str:
    return " ".join(value.lower().replace("/", " ").replace("-", " ").split())


def _error(code: str, message: str, path: str = "") -> ValidationIssue:
    return ValidationIssue("error", code, message, path)


def _warning(code: str, message: str, path: str = "") -> ValidationIssue:
    return ValidationIssue("warning", code, message, path)
