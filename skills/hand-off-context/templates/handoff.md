---
schema_version: "1.0"
handoff_id: "YYYYMMDDTHHMMSSZ-xxxx"
previous_handoff_id: null
kind: "handoff"
source_agent: "claude-code"
created_at: "YYYY-MM-DDTHH:MM:SSZ"
project: "project-name"
branch: "branch-name"
commit: "full-commit-sha"
dirty: false
---

# Handoff

## Task

現在のタスクと目的を 1〜3 文で書く。

## Context

背景・制約・前提を書く。引き継ぎ先も守るべきユーザーの指示はここに書く。

## Progress

### Completed

- 完了した作業

### In Progress

- 進行中の作業と、どこまで進んだか

### Pending

- 未着手の作業

## Decisions

### Decision 1

- Decision: 採用した方針
- Reason: 判断理由
- Alternatives: 検討した代替案と、採用しなかった理由

## Changed Files

| File | Status | Area | Description |
| --- | --- | --- | --- |
| src/example.ts | Modified | Unstaged | 変更内容 |

## Validation

| Command | Result | Note |
| --- | --- | --- |
| npm run typecheck | Passed | |
| npm run test | Not run | |

## Review Findings

`kind: "review"` のときだけ書く。`kind: "handoff"` ならこのセクションごと削除する。

| Severity | File | Finding | Suggestion |
| --- | --- | --- | --- |
| High | src/example.ts:42 | 指摘内容 | 修正案 |

## Known Issues

- 既知の問題

## Next Actions

1. 次に実施する作業
2. ユーザーへの確認が必要な事項

## Notes

補足があれば書く。なければこのセクションごと削除する。
