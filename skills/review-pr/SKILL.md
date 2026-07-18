---
name: review-pr
description: "Review a pull request against a project's style, naming, and structural conventions. Use when the user asks for a PR review, code review, or review of pending changes — including narrowed-scope requests like 'review the styling' or 'check the naming'. Provides the cross-project review procedure and output format; the concrete rules live in each project's own .claude/skills/review-pr/rules/."
---

# review-pr

複数プロジェクトで共通のコードレビュー手順・出力フォーマットを提供するスキルの**骨格**。手順・重要度分類・拡張ガイドはどのプロジェクトでも同じなので中央に置き、**具体的なレビュー観点（命名・CSS・構造などの規約本文）は各プロジェクトの `.claude/skills/review-pr/rules/` に置く**。

機械的に検出できる項目（フォーマット、未使用変数、`any` 禁止、import 順序、フック依存配列など）は各プロジェクトの `lint`・`format`・`typecheck` に任せ、本スキルは**人間の判断が必要なルール**にフォーカスする。

## いつ発動するか

次のいずれかに該当する場合に使う:

- 「PR レビューして」「コードレビューして」「変更をレビューして」と依頼された
- 「スタイルだけ見て」「命名だけチェックして」など特定観点のレビューを依頼された
- PR の差分（`git diff`、GitHub の PR、ステージング済みの変更）に対する品質評価を求められた

## このスキルの構成（骨格と本文の分離）

| 役割 | 置き場所 |
|---|---|
| レビュー手順・出力フォーマット・拡張ガイド（本ファイル） | 本リポジトリ（横断・不変の骨格） |
| 実際のレビュー観点（命名・CSS・構造などの規約本文と例） | 各プロジェクトの `.claude/skills/review-pr/rules/`・`examples/` |

各プロジェクトはスタイル基盤（例: CSS Modules と Vanilla Extract）やディレクトリ規約が異なるため、`rules/` の中身は完全に別物になる。**本ファイルをプロジェクトへ取り込む際は、そのプロジェクトの `rules/` を必ず用意する**（骨格だけでは観点が空になる）。

## レビュー手順

### 1. 差分の取得

優先順位:

1. ユーザーが PR 番号や URL を指定 → `gh pr view <番号>` / `gh pr diff <番号>` で取得（GitHub MCP が利用可能なら `mcp__github__pull_request_read` でもよい）
2. ブランチがデフォルトブランチ（`develop` / `main` 等）から派生している → `git diff <base>...HEAD --stat` と `git diff <base>...HEAD` で差分把握
3. 作業ツリーに未コミット変更がある → `git status` と `git diff`

### 2. 観点の選択

依頼内容から、そのプロジェクトの `rules/` 配下の参照ファイルを決定する。実際のカテゴリはプロジェクト側が定義するが、典型的な対応は次の通り:

| 依頼パターン | 参照ファイル（プロジェクトの `rules/` 配下） |
|---|---|
| 「PR レビュー」「全体レビュー」「コードレビュー」 | `rules/**/*.md` 全て |
| 「スタイル」「命名」「CSS」「構造」関連 | `rules/style/*.md` |
| 「命名だけ」 | `rules/style/naming.md` |
| 「CSS だけ」「クラス名だけ」 | `rules/style/css.md` |
| 「ディレクトリ構造」「ファイル配置」 | `rules/style/structure.md` |

プロジェクトが `rules/a11y/`・`rules/performance/`・`rules/i18n/` 等を追加していれば、同様に依頼内容へマッピングする。

### 3. ルールの読み込みとレビュー

選択したルールファイルを実際に読み、差分の各ファイルに対してルール違反を検出する。**ルールを推測で適用せず、必ずファイルから引用して根拠を示す。** 判断に迷ったらプロジェクトの `examples/` と既存コードを参照する。

### 4. 出力フォーマット

指摘は重要度別に整理し、ファイルパスと行番号を必ず含める。各指摘には**参照したルールファイルとセクションを引用**する。

````markdown
## レビュー結果

### 🔴 Must（規約違反・修正必須）

- **`<file>:<line>`**
  何がどのルールに違反しているかを一文で述べ、根拠として参照した `rules/...` のファイル・セクションを引用する。必要なら Bad/Good の最小コード例を添える。

### 🟡 Should（推奨される改善）

- **`<file>:<line>`**
  規約違反ではないが、既存コードと一貫させると良い点。

### 🟢 Nit（任意の好み）

- ...

### ✅ 良かった点

- 規約に正しく従えている点を挙げる。
````

## 出力上の注意

- 機械的検出可能な指摘（lint で出るもの）は基本的に書かない。書く場合は「lint で検出可能」と添える
- 「規約違反」と「好みの差」を明確に分ける（Must / Should / Nit）
- 参照したルールファイルとセクションを必ず引用する
- ファイルが大量にある PR では、まず観点別の集計（「naming 違反 N 件、css 違反 M 件」）を提示してから個別指摘に入る
- そのプロジェクトのスタイル基盤に即したコメントにする（他プロジェクトの規約を混同しない）

## 拡張ガイド（将来の作業者向け）

- **観点を増やすとき**（例: アクセシビリティ）は、対象プロジェクトの `.claude/skills/review-pr/` 側で `rules/<category>/`・`examples/<category>/` を追加し、そのプロジェクトの SKILL.md の「観点の選択」テーブルに行を足す。**本ファイル（中央の骨格）にプロジェクト固有の観点や実コードのパスを書かない。**
- **手順・出力フォーマット・重要度分類そのものを変えるとき**は本ファイルを更新する。骨格の変更は全プロジェクトへ影響するため、取り込み済みプロジェクトとの整合を確認する。
- 同じ観点が複数プロジェクトの `rules/` で実質同一になったら、その観点の共通部分も本リポジトリへ昇格できないか検討する（判断基準は `../create-skill/rules/placement.md`）。
