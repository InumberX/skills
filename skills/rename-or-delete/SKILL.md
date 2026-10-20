---
name: rename-or-delete
description: "Rename or delete code safely by finding every reference before the change and proving none are left afterwards — files, functions, components, assets, CSS classes, constants, route params, enum labels, and payload fields. Searches the whole repository (tests, E2E scenarios, docs, configs, string literals), deletes only what has zero references, reviews bulk replacements line by line, and reports the before/after search counts. Use when the user asks to rename, move, delete, remove, or clean up unused code, drop a field from a payload, check whether something is still used, or conclude that a feature or code path does not exist."
---

# rename-or-delete

識別子・ファイル・アセットを改名・削除するときに、**変更の前に参照を洗い出し、変更の後に残っていないことを示す**スキル。プロジェクトを問わず、検索の範囲と確認の順番だけを決める。

改名・削除の手戻りは、ほとんどが「探していなかった場所に参照が残っていた」ことで起きる。アプリのソース配下だけを置換してテストや E2E シナリオが壊れる、文字列リテラル内のパスまで置換して URL の判定が化ける、optional で受けている読み手に気づかずフィールドを落とす、などである。どれも着手前の検索で防げる。

## いつ発動するか

次のいずれかに該当する場合に使う:

- 「〜を改名して」「名前を変えて」「〜へ移動して」と依頼された
- 「〜を削除して」「使っていないものを消して」「未使用のコードを整理して」と依頼された
- 「このフィールドを API から外して」「この props はもう要らない」と依頼された
- 「これはまだ使われている？」「この導線は存在する？」と確認を求められた
- 自分の作業の途中で、何かを「無い」「使われていない」と結論づけようとしている

未使用変数・未使用 import のように lint や typecheck が検出するものは、ツールの結果に従う。本スキルは、ツールが見ない参照（文字列・設定・ドキュメント・別リポジトリ）を探すことに集中する。

## 参照ファイルの選択

| 状況 | 参照ファイル |
| --- | --- |
| どの改名・削除でも（最初に必ず読む） | `rules/search.md` |
| 削除する、フィールドや props を落とす、「存在しない」と結論づける | `rules/delete.md` |
| 改名・移動する、一括置換する | `rules/rename.md` |

## 手順

### 1. 対象と操作を確定する

対象（名前・種類・定義の場所）と、操作（削除 / 改名 / 移動 / 存在確認）を 1 行で書き出す。複数の対象をまとめて扱う依頼なら、**対象の一覧を先にユーザーへ示して合意を取る**。一覧に無いものは、規約に合わせたくなっても同じ変更に含めない。範囲が後から膨らむと、レビューで何を確認すればよいか分からなくなるため。

### 2. 着手前に参照を洗い出す

`rules/search.md` に従って検索する。このとき実行した検索コマンドとヒット件数を控えておく。完了報告で「何を探して、何件あったか」を示すために使う。

### 3. 変更する

操作に応じて `rules/delete.md` か `rules/rename.md` を読み、その手順で変更する。削除は、定義を除いた参照が 0 件のものだけに行う。参照が残っているのに消したい場合は、先に参照側をどうするかをユーザーに確認する。

### 4. 変更後に同じ検索をもう一度実行する

手順 2 と同じ検索を再実行し、旧名・削除した名前のヒットが 0 件になったことを確認する。意図して残すヒット（変更履歴、移行ガイド、互換のための別名など）は、1 件ずつ理由を付けて報告に挙げる。

続けて、プロジェクトの typecheck・lint・テストを実行する。export を削除・移動した場合は、ビルドまで実行する。型チェックだけでは、バンドラーの解決や動的 import の失敗を検出できないため。

## 出力フォーマット

完了報告には次を含める。

```markdown
## 変更内容
- 対象: <名前>（<種類>） / 操作: <削除 | 改名: 旧名 → 新名>

## 参照の確認
| 検索 | 変更前 | 変更後 |
| --- | --- | --- |
| `<実行した検索コマンド>` | N 件 | 0 件 |

## 意図して残したもの
- <パス:行> — <理由>（無ければ「なし」）

## 実行した検証
- <typecheck / lint / test / build のコマンドと結果>
```

検索を実行していない範囲（別リポジトリ、外部から呼ばれる API、データベースの値など）がある場合は「未確認」として明記する。「参照なし」と書かない。

## 拡張ガイド（将来の作業者向け）

新しい落とし穴を足すときは、まず既存の 3 ファイルのどれかに追記できないかを検討する。検索で見落としやすい場所は `rules/search.md`、消してよいかの判断は `rules/delete.md`、置換の手順は `rules/rename.md` に置く。特定プロジェクトのパスや識別子を例に書かない。それらは各プロジェクトの `.claude/skills/` に置く。
