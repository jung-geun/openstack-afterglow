# milestone.md — OpenSpec로 이관됨

이 프로젝트의 작업 기록은 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 구조로 이관되었습니다. 더 이상 이 단일 파일에 append하지 않습니다.

| 무엇 | 어디 |
|------|------|
| **완료 기록** (구 milestone.md 전체) | `openspec/changes/archive/<날짜-슬러그>/` — 항목별 `proposal.md` + `tasks.md`(원문 verbatim) |
| **진행 중 작업** | `openspec/changes/<슬러그>/` (없으면 진행 중 작업 없음) |
| **현황 보기** | `openspec list` |
| **옛 설계 문서** (구 상단부) | `docs/legacy-design-overview.md` |

## 새 작업 기록 방법

```bash
/opsx:propose "<아이디어>"          # 새 change 생성 (proposal + tasks)
#   작업 중 openspec/changes/<slug>/tasks.md 체크박스 갱신
/opsx:archive                       # 완료 시 아카이브
#   CLI 동등: openspec archive <slug> --skip-specs --yes
```

> 본 프로젝트는 OpenSpec의 `specs/`(현재 진실) 레이어를 두지 않는다(tasks-only `rapid` 스키마).
> 현재 기능 명세는 `docs/`와 `union.md`가 담당하므로, 아카이브 시 `--skip-specs`를 사용한다.
> 자세한 규정은 [CLAUDE.md](CLAUDE.md) "작업 기록 의무 (OpenSpec)" 참조.
