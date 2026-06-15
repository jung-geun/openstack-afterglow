#!/usr/bin/env python3
"""milestone.md → openspec/changes/archive/ 일회성 기계적 마이그레이션.

설계 원칙(무손실·기계적):
- 의미 재작성 없음. 섹션 본문은 verbatim으로 tasks.md에 보존.
- 분류 불가 섹션은 드롭하지 않고 FLAG(리포트 + flagged 보존).
- 정합성: 입력 `## ` 섹션 수 == (milestone 폴더 + meta + flagged) 합,
  입력 체크박스 총수 == 출력 체크박스 총수.

사용:
  python scripts/migrate_milestone.py            # dry-run(리포트만, 쓰기 없음)
  python scripts/migrate_milestone.py --apply     # 실제 생성
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "milestone.md"
ARCHIVE_DIR = ROOT / "openspec" / "changes" / "archive"
LEGACY_DOC = ROOT / "docs" / "legacy-design-overview.md"
REPORT = ROOT / "scripts" / "milestone-migration-report.md"

# milestone 본문이 시작되는 첫 섹션 제목(이 앞은 전부 옛 설계문서 = META)
FIRST_MILESTONE_TITLE = "## 1. Manila NFS Share 지원 추가"

# milestone 판별 패턴(번호. / 날짜 / Phase N / § N / Milestone N)
MILESTONE_RE = re.compile(
    r"^##\s+(?:\d+(?:\.\d+)?\.|\d{4}-\d{2}-\d{2}|Phase\s+\d+|§\s*\d+|Milestone\s+\d+)"
)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
CHECKBOX_RE = re.compile(r"^\s*- \[[ xX]\]")
ASCII_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]{1,}")
STOPWORDS = {"the", "and", "for", "with"}


def split_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """(preamble, [(title_line, body_including_title), ...]) 반환."""
    lines = text.splitlines(keepends=True)
    sections: list[tuple[str, str]] = []
    preamble: list[str] = []
    cur_title: str | None = None
    cur_body: list[str] = []
    for ln in lines:
        if ln.startswith("## "):
            if cur_title is not None:
                sections.append((cur_title, "".join(cur_body)))
            elif preamble:
                pass
            cur_title = ln.rstrip("\n")
            cur_body = [ln]
        else:
            if cur_title is None:
                preamble.append(ln)
            else:
                cur_body.append(ln)
    if cur_title is not None:
        sections.append((cur_title, "".join(cur_body)))
    return "".join(preamble), sections


def count_checkboxes(text: str) -> int:
    return sum(1 for ln in text.splitlines() if CHECKBOX_RE.match(ln))


def slugify(title: str, seq: int) -> str:
    """제목에서 ASCII 토큰을 뽑아 `<seq02>-<tok-tok...>` slug 생성."""
    # 선행 식별자(번호/Phase/§/Milestone) 제거
    cleaned = re.sub(r"^##\s+", "", title)
    cleaned = re.sub(r"^(?:\d+(?:\.\d+)?\.|Phase\s+\d+|§\s*\d+|Milestone\s+\d+|\d{4}-\d{2}-\d{2})\s*[—\-:]*\s*", "", cleaned)
    toks = [t.lower() for t in ASCII_TOKEN_RE.findall(cleaned) if t.lower() not in STOPWORDS]
    toks = toks[:4]
    base = f"{seq:02d}"
    return f"{base}-{'-'.join(toks)}" if toks else base


def main() -> int:
    apply = "--apply" in sys.argv
    text = SRC.read_text(encoding="utf-8")
    total_checkboxes_in = count_checkboxes(text)
    preamble, sections = split_sections(text)

    # FIRST_MILESTONE_TITLE 인덱스로 설계문서 영역 경계 결정
    first_idx = next((i for i, (t, _) in enumerate(sections) if t.strip() == FIRST_MILESTONE_TITLE), None)
    if first_idx is None:
        print(f"ERROR: '{FIRST_MILESTONE_TITLE}' 섹션을 찾지 못함 — 중단", file=sys.stderr)
        return 2

    design_sections = sections[:first_idx]      # 전부 META(옛 설계문서)
    work_sections = sections[first_idx:]         # milestone 후보

    milestones: list[tuple[str, str]] = []
    flagged: list[tuple[str, str]] = []
    for title, body in work_sections:
        if MILESTONE_RE.match(title):
            milestones.append((title, body))
        else:
            flagged.append((title, body))

    # 날짜 carry-forward(연대순 인접 가정), 선행 미상은 첫 확인 날짜로 보정
    raw_dates: list[str | None] = []
    for title, _ in milestones:
        m = DATE_RE.search(title)
        raw_dates.append(m.group(1) if m else None)
    first_known = next((d for d in raw_dates if d), "2026-04-15")
    dates: list[str] = []
    last = first_known
    for d in raw_dates:
        if d:
            last = d
        dates.append(d or last)

    # 출력 계획
    planned: list[tuple[str, str, str]] = []  # (folder, title, body)
    seen: set[str] = set()
    for seq, ((title, body), date) in enumerate(zip(milestones, dates), start=1):
        slug = slugify(title, seq)
        folder = f"{date}-{slug}"
        while folder in seen:
            folder += "-x"
        seen.add(folder)
        planned.append((folder, title, body))

    # 정합성 회계
    cb_design = sum(count_checkboxes(b) for _, b in design_sections)
    cb_pre = count_checkboxes(preamble)
    cb_ms = sum(count_checkboxes(b) for _, _, b in planned)
    cb_flag = sum(count_checkboxes(b) for _, b in flagged)
    cb_out = cb_design + cb_pre + cb_ms + cb_flag

    # 리포트
    rep = []
    rep.append("# milestone.md 마이그레이션 리포트\n")
    rep.append(f"- 입력 `## ` 섹션: {len(sections)}\n")
    rep.append(f"- 설계문서(META) 섹션: {len(design_sections)} → docs/legacy-design-overview.md\n")
    rep.append(f"- milestone 섹션: {len(milestones)} → archive 폴더 {len(planned)}개\n")
    rep.append(f"- FLAGGED(수동 처리 필요): {len(flagged)}\n")
    rep.append(f"- 체크박스: 입력 {total_checkboxes_in} == 출력 {cb_out} → {'OK' if total_checkboxes_in == cb_out else 'MISMATCH!!'}\n")
    rep.append(f"  (design {cb_design} + preamble {cb_pre} + milestones {cb_ms} + flagged {cb_flag})\n")
    rep.append("\n## FLAGGED 섹션 (드롭하지 않음 — 수동 라우팅 필요)\n")
    for t, b in flagged:
        rep.append(f"- `{t.strip()}`  (체크박스 {count_checkboxes(b)})\n")
    rep.append("\n## 생성될 archive 폴더\n")
    for folder, title, body in planned:
        rep.append(f"- `{folder}/`  ← {title.strip()}  (체크박스 {count_checkboxes(body)})\n")
    report_text = "".join(rep)
    print(report_text)

    if not apply:
        print("\n[dry-run] 쓰기 없음. 실제 생성하려면 --apply")
        return 0 if total_checkboxes_in == cb_out else 1

    # ---- 실제 생성 ----
    # 1) legacy-design-overview.md
    LEGACY_DOC.parent.mkdir(parents=True, exist_ok=True)
    legacy = ["# Afterglow — 레거시 설계 개요 (milestone.md 이관 보존)\n\n",
              "> milestone.md 상단의 옛 설계문서 영역을 verbatim 보존. 현재 진실은 `union.md`/`docs/` 참조.\n\n",
              preamble]
    for _, body in design_sections:
        legacy.append(body)
    LEGACY_DOC.write_text("".join(legacy), encoding="utf-8")

    # 2) archive 폴더들
    for folder, title, body in planned:
        d = ARCHIVE_DIR / folder
        d.mkdir(parents=True, exist_ok=True)
        date = folder.split("-")[0] + "-" + folder.split("-")[1] + "-" + folder.split("-")[2]
        clean_title = re.sub(r"^##\s+", "", title).strip()
        (d / ".openspec.yaml").write_text(f"schema: rapid\ncreated: {date}\n", encoding="utf-8")
        (d / "proposal.md").write_text(
            f"## Why\n\n레거시 milestone.md에서 이관된 완료 기록(기계 변환, 의미 무변경).\n\n"
            f"## What Changes\n\n- {clean_title}\n\n"
            f"## Impact\n\n구현 완료됨. 상세 작업 내역은 tasks.md(원문 verbatim) 참조.\n",
            encoding="utf-8",
        )
        # tasks.md = 섹션 본문 verbatim
        (d / "tasks.md").write_text(body, encoding="utf-8")

    # 3) flagged 보존(수동 처리용)
    if flagged:
        flag_dir = ARCHIVE_DIR / "_FLAGGED_FOR_MANUAL_REVIEW"
        flag_dir.mkdir(parents=True, exist_ok=True)
        for i, (t, b) in enumerate(flagged, start=1):
            (flag_dir / f"{i:02d}.md").write_text(b, encoding="utf-8")

    REPORT.write_text(report_text, encoding="utf-8")
    print(f"\n[apply] 완료: archive {len(planned)}개, flagged {len(flagged)}개, legacy 1개")
    return 0 if total_checkboxes_in == cb_out else 1


if __name__ == "__main__":
    raise SystemExit(main())
