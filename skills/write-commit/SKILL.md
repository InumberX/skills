---
name: write-commit
description: "Write commit messages and pull request descriptions that follow these projects' shared conventions — short lowercase conventional-style prefixes (feat:/fix:/refactor:/perf:/chore:/style:), focused imperative subjects, and a PR body covering summary, linked issue, and local-check confirmation. Use when the user asks to commit changes, write a commit message, or open/describe a pull request."
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

実際の履歴で使われているものに揃える:

| プレフィックス | 用途 | 例 |
|---|---|---|
| `fix:` | バグ修正・既存挙動やスタイルの修正 | `fix: header mobile button` |
| `feat:` | **機能・要素の追加はすべてこれに統一**（規模の大小を問わない） | `feat: PrimitiveButton ベースコンポーネントを追加` / `feat: home latest works` |
| `refactor:` | ランタイム挙動は変えないが、コード構造・型表現を変更する（`import type` 化・型注釈の追加・リネーム・抽出など） | `refactor: type のみで使用する import に type 修飾子を付与` |
| `perf:` | パフォーマンス改善 | `perf: 静的アセットに immutable な Cache-Control を付与` |
| `chore:` | 雑務・作業ドキュメント整理など | `chore: remove migration working docs` |
| `style:` | フォーマッタ領域の純粋な整形のみ（空白・改行・引用符・セミコロン・import 順序など）。コードの構造・型表現は変えない | `style: 長い三項演算子の改行を整える` |

> **`style:` と `refactor:` の境界**: ランタイム挙動を変えない点は共通だが、**コードの構造・型表現に手を入れるなら `refactor:`、フォーマッタで機械的に直せる整形だけなら `style:`**。したがって `import type` 化・型修飾子の付与のような**型表現の変更は `refactor:` に統一する**（過去履歴では `style:` に分類された例もあるが、境界を明確にするため今後は `refactor:` に寄せる）。なお本プロジェクト群は oxfmt が整形を自動化するため、手書きの `style:` コミットは基本的に稀。

> **`add:` は使わない（旧慣習）。** 過去の履歴には `add:` が多数あるが、Conventional Commits 標準外で `feat:` との境界も曖昧なため、新規コミットでは追加は必ず `feat:` に寄せる。過去コミットの書き換えは不要。既存の `add:` を見ても真似しない。

### プレフィックスなしの慣例

- **依存パッケージの更新は `update library` をプレフィックスなしで使う**（履歴で頻出の定型）。個別ライブラリ名を書き足してもよいが、基本はこの定型に合わせる。
- それ以外で迷ったら上表のいずれかを付ける。無理に新しいプレフィックスを増やさない。

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
