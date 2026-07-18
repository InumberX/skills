# 形式規約(Agent Skills 標準)

スキルは Anthropic の Agent Skills 標準形式で作る。この形式にしておくことで、Claude Code が `.claude/skills/` 配下のスキルを自動発見・自動発動でき、将来の公開・プラグイン配布・他ツール対応も中身の書き直しなしに行える。

## ディレクトリ構成

1 スキル = 1 ディレクトリ。`SKILL.md` のみ必須で、他は必要になったときに追加する。

```
skills/<skill-name>/
├── SKILL.md          # 必須。入口(発動条件 + 手順 + 参照ファイルへの案内)
├── rules/            # 詳細ルール。観点ごとに分割(例: rules/style/css.md)
├── examples/         # 良い例・悪い例(例: examples/style/good.md, bad.md)
├── references/       # 背景知識・外部仕様のまとめなど、読み込みが任意の資料
├── templates/        # 成果物の雛形
└── scripts/          # 決定的な処理を行う実行スクリプト
```

- 1 ファイルにすべて書かない。SKILL.md が肥大化すると「全部読むか読まないか」のモノリスになり、必要な部分だけ読める利点が消える
- 逆に、数行しかない `rules/` ファイルを乱立させない。既存ファイルへの追記で済まないか先に検討する

## 命名

| 対象 | 形式 | 例 |
|---|---|---|
| スキル名(ディレクトリ名・`name`) | ケバブケースの**動詞句**(タスク) | `review-pr`、`create-skill`、`commit-message` |
| rules/ 配下 | `<観点カテゴリ>/<観点>.md` | `rules/style/naming.md` |
| examples/ 配下 | rules/ とカテゴリを揃える | `examples/style/good.md` |

技術名だけのスキル名(`react`、`css`)は付けない。発動判断は「いま何をしようとしているか」で行われるため、タスクが見えない名前はスキルが発動しない原因になる。

## frontmatter

```yaml
---
name: create-skill
description: Create a new Agent Skill following ... Use whenever the user asks to ...
---
```

- `name`: ディレクトリ名と一致させる
- `description`: **英語**で書く(既存スキルの慣例。ツール側のマッチング精度も安定する)。次の 2 要素を必ず含める:
  1. 何をするスキルか
  2. **いつ使うか** — ユーザーの依頼パターンを具体的に列挙する(「Use when the user asks to ...」)。発動判断は description だけで行われるため、ここに書いていない発動条件は存在しないのと同じ。本文の「いつ発動するか」は description の詳細化であって代わりにはならない
- スキルが増えて必要になったら、version・tags・compatible などは frontmatter の `metadata` フィールドに追加する(独自の YAML ファイルは作らない)

## 本文の言語

本文は日本語で書く(既存スキルの慣例)。コード例・コマンド・ファイルパスは実際のものをそのまま使う。
