---
name: write-commit
description: "Write commit messages and pull request descriptions that follow these projects' shared conventions — short lowercase conventional-style prefixes (feat:/fix:/refactor:/perf:/docs:/test:/ci:/build:/chore:/revert:, with chore(deps): for dependency updates), focused imperative subjects, and a PR body covering summary, linked issue, and local-check confirmation. Use when the user asks to commit changes, write a commit message, or open/describe a pull request."
---

# write-commit

コミットメッセージと Pull Request の書き方をプロジェクト横断で揃えるスキル。プレフィックス語彙・件名の粒度・PR 本文の骨組みはどのプロジェクトでも同じなので中央に置く。ブランチ命名の自動ラベル付けなど**プロジェクト固有の運用**は各プロジェクトの `AGENTS.md` / `CLAUDE.md` を優先する。

## いつ発動するか

次のいずれかに該当する場合に使う:

- 「コミットして」「コミットメッセージを書いて」と依頼された
- 「PR を作って」「PR の説明を書いて」と依頼された
- 変更をまとめて記録・共有する文面（コミット/PR）の作成を求められた

## コミットメッセージ規約

### 形式

```
<prefix>: <imperative summary>
```

- **プレフィックスは小文字**。コロンの後に半角スペース 1 つ、件名を続ける。
- **件名は簡潔・命令形寄り**。1 コミット = 1 つの関心事に絞る。
- **件名は日本語でも英語でもよい**（既存履歴は混在。周辺コミットの言語に寄せる）。
- 詳細な理由・背景があれば本文（空行を挟んで）に書く。「何を」より「なぜ」を優先。

### プレフィックス語彙

Conventional Commits の標準型に揃える（履歴で頻出のものを上に置く）:

| プレフィックス | 用途 | 例 |
|---|---|---|
| `feat:` | **機能・要素の追加はすべてこれに統一**（規模の大小を問わない） | `feat: PrimitiveButton ベースコンポーネントを追加` / `feat: home latest works` |
| `fix:` | バグ修正・既存挙動やスタイルの修正 | `fix: header mobile button` |
| `refactor:` | ランタイム挙動は変えないが、コード構造・型表現を変更する（`import type` 化・型注釈の追加・リネーム・抽出など） | `refactor: type のみで使用する import に type 修飾子を付与` |
| `perf:` | パフォーマンス改善 | `perf: 静的アセットに immutable な Cache-Control を付与` |
| `docs:` | ドキュメントのみの変更（README・コードコメント・スキル本文など） | `docs: update readme` |
| `test:` | テストの追加・修正のみ | `test: add BaseButton interaction tests` |
| `ci:` | CI 設定・ワークフローの変更（`.github/workflows/` など） | `ci: add skill frontmatter validation` |
| `build:` | ビルドシステム・ツール・設定の変更（vite / next / wrangler 設定、ビルドスクリプトなど）。**依存パッケージの更新は `chore(deps):`** を使う | `build: adjust vite config` |
| `chore:` | 上記のどれにも当てはまらない雑務・作業ドキュメント整理・稀な純整形など | `chore: remove migration working docs` |
| `revert:` | 以前のコミットの取り消し | `revert: feat: PrimitiveButton ベースコンポーネントを追加` |

> **依存パッケージの更新は `chore(deps):`。** スコープ `(deps)` で依存更新であることを明示する（例: `chore(deps): update vite`）。過去履歴の `update library`（プレフィックスなし）は旧慣習で、今後は使わない。

> **`style:` は使わない。** 空白・引用符・import 順序などの整形は oxfmt が自動で行うため、整形だけの手書きコミットはほぼ発生しない。`import type` 化・型修飾子の付与のような**型表現・構造の変更は `refactor:`**（過去履歴に `style:` の例があるが今後は `refactor:` に統一）、フォーマッタで機械的に直せる整形のみが残る稀なケースは `chore:` に寄せる。

> **`add:` は使わない（旧慣習）。** 過去の履歴には `add:` が多数あるが、Conventional Commits 標準外で `feat:` との境界も曖昧なため、新規コミットでは追加は必ず `feat:` に寄せる。過去コミットの書き換えは不要。既存の `add:` を見ても真似しない。

### プレフィックスの選び方

- **必ず上表のいずれかのプレフィックスを付ける。** 迷ったら変更の主目的で選ぶ（挙動修正=`fix:`、機能追加=`feat:`、挙動を変えない構造変更=`refactor:`）。
- **無理に新しいプレフィックスを増やさない。** 上表（Conventional Commits 標準型）で表現できないケースはまず `chore:` に寄せる。
- 過去履歴に散見されるプレフィックスなしのコミット（`update library`、英文の平叙文など）は旧慣習。**今後は真似せず、必ずプレフィックスを付ける**（依存更新は `chore(deps):`）。

> `(#NNN)` の PR 番号は squash マージ時に自動で付く。ローカルのコミット件名に手で付けない。

## Pull Request 規約

PR 本文には最低限これらを含める:

- **概要**: 何を・なぜ変更したかの簡潔な説明
- **関連 Issue / タスク**: あればリンクする
- **UI 変更**: スクリーンショットまたは Storybook の参照を添える
- **ローカルチェック**: プロジェクトの標準チェック（例: `npm run pre-commit` = typecheck / lint / format 等。コマンド名はリポジトリにより異なる）をローカルで通したことを明記する
- **影響範囲の明示**: 設定・依存関係・テストに影響する変更は本文で明示的に呼びかける

PR タイトルもコミットと同じプレフィックス規約に従う。

> **プロジェクト固有の運用に注意**: ブランチ命名による自動ラベル付け（例: `feature/*` → enhancement、`bugfix/*` / `hotfix/*` → bug）など、リポジトリごとに異なる運用がある。**中央の本スキルには固有ルールを書かず、対象プロジェクトの `AGENTS.md` を確認して従う。**

## 出力上の注意

- ステージ済みの差分（`git diff --staged`）を確認し、実際の変更内容に即した件名を書く。差分と食い違う定型文を使わない。
- 無関係な変更が混ざっていたら、コミットを分けることを提案する。
- テンプレートがあるプロジェクト（`.github/pull_request_template.md` 等）では、その節構成に本文を流し込む。

## 拡張ガイド（将来の作業者向け）

- 履歴で新しいプレフィックスが定着したら、上の語彙表に追記する（推測で増やさない。実績で判断する）。
- 特定プロジェクトだけの運用（ブランチ命名・ラベル・レビュー必須人数など）は本ファイルに書かず、そのプロジェクトの `AGENTS.md` / `CLAUDE.md` に置く。
- コミット規約を CI（commitlint 等）で機械検証するようになったら、機械検出できる項目は本スキルから外し、CI に委ねる。
