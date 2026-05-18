"""End-to-end statik tarama: repo path → IssueCandidate listesi.

CLI:
    python -m analysis.scan <repo_path>
    python -m analysis.scan <repo_path> --json
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from analysis.ast_parser import ParsedFile, parse_file
from analysis.file_walker import walk_files
from analysis.static_rules import ALL_PROJECT_RULES, ALL_RULES, IssueCandidate


@dataclass
class ScanReport:
    repo_path: str
    files_scanned: int
    issues: list[IssueCandidate]
    duration_ms: int

    def to_dict(self) -> dict:
        return {
            "repo_path": self.repo_path,
            "files_scanned": self.files_scanned,
            "issues_count": len(self.issues),
            "duration_ms": self.duration_ms,
            "issues": [i.to_dict() for i in self.issues],
        }


def scan_repo(repo_path: Path | str, *, languages: list[str] | None = None) -> ScanReport:
    """Verilen repo dizini üzerinde tüm kuralları çalıştır."""
    repo_path = Path(repo_path).resolve()
    start = time.monotonic()

    file_infos = walk_files(repo_path, languages=languages or ["python"])
    parsed_files: list[ParsedFile] = []
    for fi in file_infos:
        pf = parse_file(fi.abs_path)
        if pf is None:
            continue
        # rel_path'i file alanı olarak kullan — terminal çıktısı temiz olsun
        pf.file_path = fi.rel_path
        parsed_files.append(pf)

    issues: list[IssueCandidate] = []

    # Tek-dosya kurallar
    for pf in parsed_files:
        for rule in ALL_RULES:
            try:
                issues.extend(rule.scan(pf))
            except Exception as e:  # pragma: no cover — rule guards her zaman çalışmalı
                # Bir kuralın patlaması diğerlerini durdurmasın
                print(f"[WARN] Rule {rule.code} {pf.file_path} üzerinde patladı: {e}")

    # Proje seviyesi kurallar
    for prule in ALL_PROJECT_RULES:
        try:
            issues.extend(prule.scan_project(parsed_files))
        except Exception as e:  # pragma: no cover
            print(f"[WARN] Project rule {prule.code} patladı: {e}")

    # Stabil sıralama: severity (high→low), sonra dosya, sonra satır
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: (sev_rank.get(i.severity, 9), i.file, i.line_start, i.code))

    duration = int((time.monotonic() - start) * 1000)
    return ScanReport(
        repo_path=str(repo_path),
        files_scanned=len(parsed_files),
        issues=issues,
        duration_ms=duration,
    )


def _format_text(report: ScanReport) -> str:
    """İnsanca okunabilir özet (terminal için)."""
    lines: list[str] = []
    lines.append(f"Repo: {report.repo_path}")
    lines.append(
        f"Taranan dosya: {report.files_scanned}  |  Bulgu: {len(report.issues)}  "
        f"|  Süre: {report.duration_ms} ms"
    )
    if not report.issues:
        lines.append("(temiz!)")
        return "\n".join(lines)

    by_sev = {"high": 0, "medium": 0, "low": 0}
    by_code: dict[str, int] = {}
    for i in report.issues:
        by_sev[i.severity] += 1
        by_code[i.code] = by_code.get(i.code, 0) + 1

    lines.append(f"Severity: high={by_sev['high']}  medium={by_sev['medium']}  low={by_sev['low']}")
    lines.append("")
    lines.append("Bulgular:")
    for i in report.issues:
        lines.append(
            f"  [{i.severity:6}] {i.code:24}  {i.file}:{i.line_start}"
        )
    lines.append("")
    lines.append("Özet (kod bazlı):")
    for code, n in sorted(by_code.items(), key=lambda x: -x[1]):
        lines.append(f"  {code:24} x{n}")
    return "\n".join(lines)


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="analysis.scan")
    parser.add_argument("repo_path", help="Yerel repo klasörü")
    parser.add_argument("--json", action="store_true", help="JSON çıktı")
    args = parser.parse_args()

    report = scan_repo(args.repo_path)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_format_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
