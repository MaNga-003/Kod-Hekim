"""End-to-end statik tarama: repo path → IssueCandidate listesi."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from analysis.ast_parser import ParsedFile, parse_file
from analysis.file_walker import count_all_source_files, walk_files
from analysis.js_ts_scan import scan_js_ts, scan_text_rules
from analysis.languages import SUPPORTED_LANGUAGES, resolve_languages
from analysis.static_rules import ALL_PROJECT_RULES, ALL_RULES, IssueCandidate

logger = logging.getLogger(__name__)


@dataclass
class ScanReport:
    repo_path: str
    files_discovered: int
    files_scanned: int
    files_unreadable: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    language_files: dict[str, int] = field(default_factory=dict)
    issues: list[IssueCandidate] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "repo_path": self.repo_path,
            "files_discovered": self.files_discovered,
            "files_scanned": self.files_scanned,
            "files_unreadable": self.files_unreadable,
            "languages": self.languages,
            "language_files": self.language_files,
            "issues_count": len(self.issues),
            "duration_ms": self.duration_ms,
            "issues": [i.to_dict() for i in self.issues],
        }


def scan_repo(repo_path: Path | str, *, languages: list[str] | None = None) -> ScanReport:
    repo_path = Path(repo_path).resolve()
    start = time.monotonic()

    langs = resolve_languages(repo_path, languages)
    total_on_disk = count_all_source_files(repo_path)
    file_infos = walk_files(repo_path, languages=langs)
    parsed_files: list[ParsedFile] = []
    unreadable: list[str] = []

    for fi in file_infos:
        pf = parse_file(fi.abs_path, language=fi.language)
        if pf is None:
            unreadable.append(fi.rel_path)
            logger.error("Okunamadı (disk): %s", fi.rel_path)
            continue
        pf.file_path = fi.rel_path
        parsed_files.append(pf)
        if not pf.parse_ok:
            logger.info(
                "Parse kısmi/başarısız ama taranıyor: %s (%s)",
                fi.rel_path,
                pf.parse_note or "metin kuralları",
            )

    if file_infos and not parsed_files:
        logger.error(
            "Repo'da %d kaynak dosya bulundu ama hiçbiri okunamadı: %s",
            len(file_infos),
            repo_path,
        )

    issues: list[IssueCandidate] = []

    python_files = [pf for pf in parsed_files if pf.is_python]
    js_ts_files = [pf for pf in parsed_files if not pf.is_python]

    for pf in python_files:
        if pf.has_ast:
            for rule in ALL_RULES:
                if pf.language not in rule.languages:
                    continue
                try:
                    issues.extend(rule.scan(pf))
                except Exception as e:
                    logger.warning("Rule %s %s: %s", rule.code, pf.file_path, e)
        else:
            try:
                issues.extend(scan_text_rules(pf))
            except Exception as e:
                logger.warning("Python metin scan %s: %s", pf.file_path, e)

    for pf in js_ts_files:
        try:
            issues.extend(scan_js_ts(pf))
        except Exception as e:
            logger.warning("JS/TS scan %s: %s", pf.file_path, e)

    for prule in ALL_PROJECT_RULES:
        ast_python = [pf for pf in python_files if pf.has_ast]
        if not ast_python:
            continue
        try:
            issues.extend(prule.scan_project(ast_python))
        except Exception as e:
            logger.warning("Project rule %s: %s", prule.code, e)

    sev_rank = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: (sev_rank.get(i.severity, 9), i.file, i.line_start, i.code))

    lang_counts: dict[str, int] = {}
    for pf in parsed_files:
        lang_counts[pf.language] = lang_counts.get(pf.language, 0) + 1

    duration = int((time.monotonic() - start) * 1000)
    logger.info(
        "Scan %s: on_disk=%d capped=%d scanned=%d issues=%d langs=%s unreadable=%d",
        repo_path,
        total_on_disk,
        len(file_infos),
        len(parsed_files),
        len(issues),
        langs,
        len(unreadable),
    )

    return ScanReport(
        repo_path=str(repo_path),
        files_discovered=total_on_disk,
        files_scanned=len(parsed_files),
        files_unreadable=unreadable,
        languages=langs,
        language_files=lang_counts,
        issues=issues,
        duration_ms=duration,
    )


def _format_text(report: ScanReport) -> str:
    lines: list[str] = []
    lines.append(f"Repo: {report.repo_path}")
    lines.append(f"Diller: {', '.join(report.languages)}")
    lines.append(
        f"Bulunan: {report.files_discovered}  Taranan: {report.files_scanned}  "
        f"Bulgu: {len(report.issues)}  Süre: {report.duration_ms} ms"
    )
    if report.files_unreadable:
        lines.append(f"Okunamayan: {len(report.files_unreadable)}")
    if not report.issues:
        lines.append("(bulgu yok)")
        return "\n".join(lines)

    by_sev = {"high": 0, "medium": 0, "low": 0}
    for i in report.issues:
        by_sev[i.severity] += 1
    lines.append(f"Severity: high={by_sev['high']}  medium={by_sev['medium']}  low={by_sev['low']}")
    for i in report.issues[:30]:
        lines.append(f"  [{i.severity:6}] {i.code:24}  {i.file}:{i.line_start}")
    return "\n".join(lines)


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="analysis.scan")
    parser.add_argument("repo_path", help="Yerel repo klasörü")
    parser.add_argument("--json", action="store_true", help="JSON çıktı")
    args = parser.parse_args()

    report = scan_repo(args.repo_path, languages=list(SUPPORTED_LANGUAGES))

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_format_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
