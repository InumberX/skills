# skills

AI コーディングエージェント向けのスキル（Agent Skills 標準形式）を貯めるリポジトリ。運用方針の詳細は [Issue #1](https://github.com/InumberX/skills/issues/1) を参照。

## 構成

```text
skills/
└── <skill-name>/         # 1 スキル = 1 ディレクトリ（タスク単位・ケバブケースの動詞句）
    ├── SKILL.md          # 必須。frontmatter(name / description)+ 手順
    └── rules/ examples/ templates/ ...   # 必要に応じて分割ファイル
```

## 役割分担

| 置き場所 | 役割 |
| --- | --- |
| 各リポジトリの `CLAUDE.md` | プロジェクトの地図（常時読み込み） |
| 各リポジトリの `.claude/skills/` | プロジェクト固有のタスク手順。**実コードのパスを引用するルールはこちら** |
| 本リポジトリ | プロジェクト横断のタスク手順・規約 |

同じスキルが 2 つ以上のリポジトリにコピーされたら、共通部分の本リポジトリへの昇格を検討する。詳細な判断基準は [`skills/create-skill/rules/placement.md`](./skills/create-skill/rules/placement.md) を参照。

## スキルの作り方

新しいスキルは [`skills/create-skill/`](./skills/create-skill/) の手順に従って作成する。

## 取り込み方法

### 1. プラグインマーケットプレイス（推奨）

本リポジトリは Claude Code の**プラグインマーケットプレイス**として公開している(`.claude-plugin/marketplace.json`)。**一括**でも**個別**でも導入できる。

```bash
# マーケットプレイスを登録（初回のみ。登録だけではインストールされない）
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

`review-pr` だけは例外的に観点本文(`rules/security/`)を同梱しており、フレームワーク・プラットフォーム由来のセキュリティ観点は取り込み先で追加設定なしに使える。スタイル・命名などの観点は従来どおり各プロジェクトの `.claude/skills/review-pr/rules/` に置く。

> **一括と個別はどちらか一方を選ぶ。** 両方入れると同じスキルが二重にロードされる（名前空間が別々なので壊れはしないが冗長）。
>
> バージョンを固定していないため、`marketplace.json` 更新時点の最新スキルが配布される。特定版に固定したい場合は各エントリに `version` を付ける。

### 2. 手動コピー

マーケットプレイスを使わない場合は、使いたいスキルを各プロジェクトの `.claude/skills/` へ手動コピーする。取り込み先で改善したら本リポジトリに還元する。

### 公開物の検査

`scripts/validate_marketplace.py` が `marketplace.json` の妥当性と `skills/` ディレクトリとの同期（登録漏れ・削除済みエントリの残存）を機械的に検査する。`.github/workflows/validate.yml` が push(main) と全 PR で自動実行するため、スキルを追加・削除したら `marketplace.json` のエントリも合わせて更新する（ローカルでは `python3 scripts/validate_marketplace.py`）。

## 検査の一覧

CI（`.github/workflows/validate.yml`）で自動実行する。ローカルでも同じコマンドで再現できる。

| 対象 | コマンド | 内容 |
| --- | --- | --- |
| SKILL.md の frontmatter | `python3 scripts/validate_skills.py` | `name` / `description` の有無、ケバブケース、ディレクトリ名との一致、ダブルクォート |
| マーケットプレイス | `python3 scripts/validate_marketplace.py` | `marketplace.json` と `skills/` の同期 |
| 日本語の括弧 | `python3 scripts/validate_text.py` | 日本語を囲む半角括弧、全角と半角が対応していない括弧 |
| ユニットテスト | `python3 -m unittest discover -s tests -p "test_*.py"` | 上記バリデータのテスト |
| Markdown の構造 | `npm run lint-markdown` | 見出し・テーブル・コードフェンスの記法（markdownlint） |
| 日本語の文章 | `npm run lint-text` | 箇条書きの句点統一など（textlint） |
| Python | `ruff check` / `ruff format --check` | lint と整形 |

`lint-markdown` と `lint-text` には `-fix` 版がある。**括弧の検査を textlint ではなく専用スクリプトで行っているのは意図的**で、textlint の `4.3.1.丸かっこ（）` は見出し・テーブル・引用を検査対象から外すうえ、自動修正が開き括弧だけを全角へ変えて閉じ括弧を半角のまま残すことがあるため。無効化した各ルールの判断根拠は `.textlintrc.yml` にコメントとして書いてある。

textlint のルール名は**報告される ID と完全に一致させる**。1文字でも違うと一致せず、無効化したつもりのルールが有効なまま残る。設定を変えたら `npx textlint --print-config` で実際に外れたかを確認すること。

Node の依存は文章検査のためだけにあり、スキル本体は Markdown のみで動く。

検査対象の glob は `.markdownlint-cli2.jsonc` の `globs`、`package.json` の `lint-text`、`scripts/validate_text.py` の `TARGETS` の3箇所にある。textlint は対象を設定ファイルに書けないため一元化できていない。**対象を変えるときは3箇所そろえる。** 揃っていないと、そのツールだけ検査せずに成功として通る。

`.npmrc` の `min-release-age=1` により、依存を追加・更新するときに公開から1日経過したパッケージのみが選ばれる。**効くのは手元で `npm install` / `npm update` を実行するときだけ**で、そこに npm 11.6 以降が要る（Node 24 に同梱されるものが該当する）。CI が実行する `npm ci` はロックファイルの内容をそのまま入れるため、公開日を再確認しない。
