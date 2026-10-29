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

Claude Code と Codex のどちらにも、プラグインとして導入できる。どちらも同じ `skills/` を配布するため、スキル本文に違いはない。

| | Claude Code | Codex |
| --- | --- | --- |
| 配布設定 | `.claude-plugin/marketplace.json`・`.claude-plugin/plugin.json` | `.agents/plugins/marketplace.json`・`.codex-plugin/plugin.json` |
| 導入できる単位 | 全部入り・個別 | 全部入りのみ |
| 明示的な呼び出し | `/review-pr` | `$inumberx-skills:review-pr` |

### 1. Claude Code: プラグインマーケットプレイス（推奨）

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

インストールしたスキルは自動発見・自動発動され、スラッシュ形式では `/review-pr` のように呼び出せる。配布しているプラグインは、全部入りの `inumberx-skills` と、個別の `create-branch` / `create-pr` / `create-skill` / `hand-off-context` / `investigate-failure` / `record-lesson` / `refine-request` / `rename-or-delete` / `review-pr` / `verify-completion` / `write-commit`。

`review-pr` だけは例外的に観点本文(`rules/security/`)と、レビューの進め方(`rules/process.md`)を同梱しており、フレームワーク・プラットフォーム由来のセキュリティ観点と、指摘の根拠の確かめ方は取り込み先で追加設定なしに使える。スタイル・命名などの観点は従来どおり各プロジェクトの `.claude/skills/review-pr/rules/` に置く。

> **一括と個別はどちらか一方を選ぶ。** 両方入れると同じスキルが二重にロードされる（名前空間が別々なので壊れはしないが冗長）。
>
> バージョンを固定していないため、`marketplace.json` 更新時点の最新スキルが配布される。特定版に固定したい場合は各エントリに `version` を付ける。

### 2. Codex: プラグインマーケットプレイス

本リポジトリは Codex の**プラグインマーケットプレイス**としても公開している(`.agents/plugins/marketplace.json`)。Codex CLI 0.163.0 で、空の `CODEX_HOME` から登録・インストールし、全 10 スキルが認識されることを確認した。

```bash
# マーケットプレイスを登録（初回のみ。登録だけではインストールされない）
codex plugin marketplace add InumberX/skills

# 全部入りプラグインをインストール
codex plugin add inumberx-skills@inumberx-skills

# 導入状態を確認（STATUS が installed, enabled になる）
codex plugin list
```

更新を取り込む:

```bash
codex plugin marketplace upgrade inumberx-skills
```

新しいコミットを取得すると、インストール済みのプラグインも入れ直される。プラグイン側の `version` を上げる必要はない。

インストールしたスキルは `inumberx-skills:<スキル名>` という名前で自動発見・自動発動される。明示的に呼び出すときは `$inumberx-skills:review-pr` のように書く。アンインストールは `codex plugin remove inumberx-skills@inumberx-skills`、マーケットプレイスの登録解除は `codex plugin marketplace remove inumberx-skills` で行う。

対応するクライアントは、`codex plugin` サブコマンドを持つ Codex CLI。Codex CLI 0.163.0 で確認した。登録内容は `~/.codex/config.toml`（`CODEX_HOME`）に保存される。同じ設定を読む IDE 拡張や Codex アプリでも使えるはずだが、動作は確認していない。

Claude Code との違いは次のとおり。

- **個別インストールはできない。** Codex はプラグインのルート直下の `skills/`、または `plugin.json` の `skills` で指定したパスからスキルを読み込み、この指定に `./` は使えない。個別プラグインのルートになる `skills/<name>/` には `SKILL.md` が直下にあるだけなので、スキルとして認識されない。
- **`.agents/plugins/marketplace.json` が `.claude-plugin/marketplace.json` より優先される。** Codex はこれがあると Claude 用のカタログを読まないため、Claude 用の個別エントリは Codex には出てこない。
- **`review-pr` の汎用の脆弱性検出は Claude Code 組み込みの `/security-review` が前提になっている。** Codex には同じものがないため、汎用の検出は実施していないことをレビュー結果に書く（`skills/review-pr/SKILL.md`）。

### 3. 手動コピー

マーケットプレイスを使わない場合は、使いたいスキルを各プロジェクトにコピーする。置き場所は Claude Code が `.claude/skills/`、Codex が `.agents/skills/` である（パスは [Codex の公式ドキュメント](https://developers.openai.com/codex/skills) で確認する）。取り込み先で改善したら本リポジトリに還元する。

```text
project/
├── .agents/skills/hand-off-context/   # Codex 用。skills/hand-off-context/ をコピーする
└── .claude/skills/hand-off-context/   # Claude Code 用。プラグインで導入するなら不要
```

両方に同じ実体を置きたい場合は、`.claude/skills/hand-off-context` から `../../.agents/skills/hand-off-context` へのシンボリックリンクにしてもよい。Windows ではシンボリックリンクに開発者モードと `git config core.symlinks true` が要るため、コピーを標準とする。

`hand-off-context` は Claude Code と Codex の間で作業を引き継ぐスキルなので、両方に入れておく。呼び出しは Claude Code が `/hand-off-context export`、Codex が `$hand-off-context import` になる（プラグインで導入した場合は `$inumberx-skills:hand-off-context import`）。引き継ぎ内容は取り込み先の `.handoff/` に保存され、`.handoff/.gitignore` によって Git の管理対象から外れる。

### 公開物の検査

`scripts/validate_marketplace.py` は、Claude Code 用の `marketplace.json` の妥当性と、`skills/` ディレクトリとの同期（登録漏れ・削除済みエントリの残存）を機械的に検査する。スキルを追加・削除したら、`marketplace.json` のエントリも合わせて更新する。

`scripts/validate_codex_plugin.py` は、Codex 用の 2 ファイルを検査する。

- 名前が Claude 用のカタログと一致している。
- 全部入りのエントリが 1 件だけで、リポジトリ直下を指している。
- `policy` と `category` の値が正しい。
- `plugin.json` の `skills` が `skills/` を指している。

Codex 向けは `skills/` を丸ごと配布するので、スキルを追加・削除しても Codex 用のファイルは変わらない。全部入りの説明文に並ぶスキル一覧だけは更新する。

どちらも `.github/workflows/validate.yml` が push(main) と全 PR で自動実行する。ローカルでは `python3 scripts/validate_marketplace.py` と `python3 scripts/validate_codex_plugin.py` で確認できる。

## 検査の一覧

CI（`.github/workflows/validate.yml`）で自動実行する。ローカルでも同じコマンドで再現できる。

| 対象 | コマンド | 内容 |
| --- | --- | --- |
| SKILL.md の frontmatter | `python3 scripts/validate_skills.py` | `name` / `description` の有無、ケバブケース、ディレクトリ名との一致、ダブルクォート、長さ（`name` は 64 文字、`description` は 1024 文字まで） |
| マーケットプレイス | `python3 scripts/validate_marketplace.py` | `marketplace.json` と `skills/` の同期 |
| Codex 用の配布設定 | `python3 scripts/validate_codex_plugin.py` | `.agents/plugins/marketplace.json`・`.codex-plugin/plugin.json` の妥当性と、`skills/` を配布対象にしていること |
| 日本語の括弧 | `python3 scripts/validate_text.py` | 日本語を囲む半角括弧、全角と半角が対応していない括弧 |
| ユニットテスト | `python3 -m unittest discover -s tests -p "test_*.py"` | 上記バリデータと、`hand-off-context` の補助スクリプト（`scripts/handoff_tool.py`）のテスト |
| Markdown の構造 | `npm run lint-markdown` | 見出し・テーブル・コードフェンスの記法（markdownlint） |
| 日本語の文章 | `npm run lint-text` | 箇条書きの句点統一など（textlint） |
| Python | `ruff check` / `ruff format --check` | lint と整形 |

`lint-markdown` と `lint-text` には `-fix` 版がある。**括弧の検査を textlint ではなく専用スクリプトで行っているのは意図的**で、textlint の `4.3.1.丸かっこ（）` は見出し・テーブル・引用を検査対象から外すうえ、自動修正が開き括弧だけを全角へ変えて閉じ括弧を半角のまま残すことがあるため。無効化した各ルールの判断根拠は `.textlintrc.yml` にコメントとして書いてある。

textlint のルール名は**報告される ID と完全に一致させる**。1文字でも違うと一致せず、無効化したつもりのルールが有効なまま残る。設定を変えたら `npx textlint --print-config` で実際に外れたかを確認すること。

Node の依存は文章検査のためだけにあり、スキル本体は Markdown のみで動く。`hand-off-context` の補助スクリプトは Python がある環境でだけ使う任意のもので、標準ライブラリしか使わない。

検査対象の glob は `.markdownlint-cli2.jsonc` の `globs`、`package.json` の `lint-text`、`scripts/validate_text.py` の `TARGETS` の3箇所にある。textlint は対象を設定ファイルに書けないため一元化できていない。**対象を変えるときは3箇所そろえる。** 揃っていないと、そのツールだけ検査せずに成功として通る。

`.npmrc` の `min-release-age=1` により、依存を追加・更新するときに公開から1日経過したパッケージのみが選ばれる。**効くのは手元で `npm install` / `npm update` を実行するときだけ**で、そこに npm 11.6 以降が要る（Node 24 に同梱されるものが該当する）。CI が実行する `npm ci` はロックファイルの内容をそのまま入れるため、公開日を再確認しない。
