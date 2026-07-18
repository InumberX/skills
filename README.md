# skills

AI コーディングエージェント向けのスキル(Agent Skills 標準形式)を貯めるリポジトリ。運用方針の詳細は [Issue #1](https://github.com/InumberX/skills/issues/1) を参照。

## 構成

```
skills/
└── <skill-name>/         # 1 スキル = 1 ディレクトリ(タスク単位・ケバブケースの動詞句)
    ├── SKILL.md          # 必須。frontmatter(name / description)+ 手順
    └── rules/ examples/ templates/ ...   # 必要に応じて分割ファイル
```

## 役割分担

| 置き場所 | 役割 |
|---|---|
| 各リポジトリの `CLAUDE.md` | プロジェクトの地図(常時読み込み) |
| 各リポジトリの `.claude/skills/` | プロジェクト固有のタスク手順。**実コードのパスを引用するルールはこちら** |
| 本リポジトリ | プロジェクト横断のタスク手順・規約 |

同じスキルが 2 つ以上のリポジトリにコピーされたら、共通部分の本リポジトリへの昇格を検討する。詳細な判断基準は [`skills/create-skill/rules/placement.md`](./skills/create-skill/rules/placement.md) を参照。

## スキルの作り方

新しいスキルは [`skills/create-skill/`](./skills/create-skill/) の手順に従って作成する。

## 取り込み方法(当面)

使いたいスキルを各プロジェクトの `.claude/skills/` へ手動コピーする。取り込み先で改善したら本リポジトリに還元する。外部公開(GitHub Pages 等)・同期の自動化は必要になってから導入する。
