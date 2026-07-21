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

## 取り込み方法

### 1. プラグインマーケットプレイス(推奨)

本リポジトリは Claude Code の**プラグインマーケットプレイス**として公開している(`.claude-plugin/marketplace.json`)。**一括**でも**個別**でも導入できる。

```bash
# マーケットプレイスを登録(初回のみ。登録だけではインストールされない)
/plugin marketplace add InumberX/skills
```

**一括インストール** — 全スキルをまとめて入れる:

```bash
/plugin install inumberx-skills@inumberx-skills
```

**個別インストール** — 使いたいスキルだけ入れる:

```bash
/plugin install review-pr@inumberx-skills
/plugin install write-commit@inumberx-skills
```

更新を取り込む:

```bash
/plugin marketplace update inumberx-skills
```

インストールしたスキルは自動発見・自動発動され、スラッシュ形式では `/review-pr` のように呼び出せる。配布しているプラグインは、全部入りの `inumberx-skills` と、個別の `create-pr` / `create-skill` / `review-pr` / `write-commit`。

> **一括と個別はどちらか一方を選ぶ。** 両方入れると同じスキルが二重にロードされる(名前空間が別々なので壊れはしないが冗長)。
>
> バージョンを固定していないため、`marketplace.json` 更新時点の最新スキルが配布される。特定版に固定したい場合は各エントリに `version` を付ける。

### 2. 手動コピー

マーケットプレイスを使わない場合は、使いたいスキルを各プロジェクトの `.claude/skills/` へ手動コピーする。取り込み先で改善したら本リポジトリに還元する。

### 公開物の検査

`scripts/validate_marketplace.py` が `marketplace.json` の妥当性と `skills/` ディレクトリとの同期(登録漏れ・削除済みエントリの残存)を機械的に検査する。`.github/workflows/validate-skills.yml` が push(main) と全 PR で自動実行するため、スキルを追加・削除したら `marketplace.json` のエントリも合わせて更新する(ローカルでは `python3 scripts/validate_marketplace.py`)。
