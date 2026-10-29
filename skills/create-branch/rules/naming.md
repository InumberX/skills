# ブランチ名の付け方

作業用のブランチ名を決めるときに読む。プロジェクトの `AGENTS.md` / `CLAUDE.md` に命名の決まりがあれば、そちらを優先する。

## 形式

```text
<prefix>/<slug>
```

- 種類を接頭辞にして `/` で区切る形は、[Conventional Branch](https://conventional-branch.github.io/) と同じ。種類が名前の先頭にあると、ブランチの一覧や補完で種類ごとにまとまる。ただし語彙は Conventional Branch（`feature` / `bugfix` / `hotfix` など）ではなく、次の `write-commit` の語彙に揃える
- `<prefix>` は `write-commit` のプレフィックス語彙（`feat` / `fix` / `refactor` / `perf` / `docs` / `test` / `ci` / `build` / `chore` / `revert`）から選ぶ。ブランチで主に行う変更に合わせ、予定している PR のタイトルのプレフィックスと揃える。コミットと別の語彙を持つと、どちらを使うか毎回迷う
- 旧慣習の `feature/<prefix>-<slug>`（`feature/fix-word-break`）と `add` は使わない。`feature/` はブランチ名でラベルを自動付与していたころの共通の入口で、その仕組みはすでに無い。`add` はコミットで使わないのと同じ理由で、`feat` と境界が曖昧になる。既存のブランチを付け直す必要は無い

## slug

- **英小文字・数字・ハイフンだけ**で書く。日本語・空白・大文字・`_` は使わない。日本語はシェルの補完や URL のエンコードで扱いにくく、大文字は大文字小文字を区別しないファイルシステム（macOS の既定）で別名のブランチと衝突する
- 2〜5 語程度で、何を変えるかが分かる名詞句にする（`word-break`、`header-mobile-button`）。PR のタイトルを縮めたものと考える
- `/` を slug の中で使わない。`fix/header/mobile` のように階層が増えると、`fix/header` という名前のブランチと共存できない（Git は同名のファイルとディレクトリを同時に持てない）
- Issue があれば番号を含めてよい（`fix/115-open-items`）。含めるかはプロジェクトの決まりに従う

## 定期作業

依存パッケージの更新のように同じ作業を繰り返すものは、日付と連番を付ける:

```text
chore/update-library-YYYYMMDDNNN
```

例: `chore/update-library-20261029001`。同じ日に 2 本目を切るときは `002` にする。日付は作業を始めた日（JST）にする。種類が `chore` なのは、コミットの `chore(deps):` に揃えるため（ブランチ名に `(deps)` は使えない）。

## 先行のブランチに重ねる

先行の PR に重ねる後続のブランチは、先行の名前の後ろに部分を足す:

```text
feat/remix3               # 先行（親）
feat/remix3-home          # 親から切った後続
feat/remix3-drinks-list
```

親の名前を頭に残すと、ブランチの一覧で親子がまとまって並び、どれがどの PR に重なっているかが分かる。`feat/remix3/home` のように `/` で区切ると、親の `feat/remix3` と共存できない（上記）。後続の種類が親と違っても（親が `feat`、後続が `fix`）、親の名前を優先する。

## 例

```text
# Good
fix/word-break
feat/home-latest-works
ci/dependabot-actions
chore/update-library-20261029001

# Bad
feature/fix-word-break           # 旧慣習 → fix/word-break
feat/add-drinkability-tag        # 種類が二重 → feat/drinkability-tag
fix                              # 何を直すのか分からない
fix/ヘッダー修正                  # 日本語
Fix/Header_Button                # 大文字と _
bugfix/header                    # write-commit に無い語彙 → fix/header
feat/remix3/home                 # 親 feat/remix3 と共存できない → feat/remix3-home
```

## 付けたあと

- 一度 push したブランチ名は、レビューや CI の途中で勝手に変えない。PR の head が変わり、レビューのコメントや CI の履歴が別の PR に分かれる。変えたい場合はユーザーに確認する
- 実行環境が自動で付けた名前（`claude/...` など）は、その環境の指定として扱い、この規約に合わせて付け直さない
