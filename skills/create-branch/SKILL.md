---
name: create-branch
description: "Create a working git branch following these projects' conventions — check the working tree, use the branch the user or the environment designates, determine the base branch (develop vs main, or the preceding PR's branch when stacking), branch from the freshly fetched remote base without tracking it (or from the current HEAD when work is already committed there), and name it <prefix>/<slug> with write-commit's prefix vocabulary. Covers both flows in use: GitHub Flow (main only) and a simplified Git Flow (feature work off develop, develop to main by release PR). Use when the user asks to create, cut, start, or switch to a new branch, to start work on a new feature or fix, or asks what a branch should be named. Pushing and opening the PR belong to the create-pr skill."
---

# create-branch

作業用の Git ブランチを作るスキル。ベースの判定・最新化・命名・作成までを扱い、push と PR の作成は `create-pr` に任せる。ベースブランチや命名の決まりがプロジェクトにある場合は、そちらを優先する（`AGENTS.md` / `CLAUDE.md`）。

## いつ発動するか

次のいずれかに該当する場合に使う:

- 「ブランチを作って」「ブランチを切って」「新しいブランチで作業して」と依頼された
- 新しい機能・修正・依存の更新に取りかかるよう依頼され、まだ作業用のブランチが無い
- 「このブランチ名でいい？」「ブランチ名を考えて」と相談された
- 先行の PR に重ねる後続の作業を始める

## 参照ファイルの選択

| 状況 | 参照ファイル |
| --- | --- |
| ブランチ名を決める（毎回読む） | `rules/naming.md` |
| 先行の PR に重ねる、同じ変更を複数のリポジトリへ入れる | `../create-pr/rules/split-and-stack.md` |

## 手順

### 1. 指定されたブランチ名が無いか確かめる

ユーザー、または実行環境（クラウドのセッション・CI など）がブランチ名を指定している場合は、その名前を使い、手順 4 の命名を飛ばす（手順 5 以降は同じ）。指定を無視して規約どおりの名前で作ると、指定先へ push できない、あるいは別のブランチに作業が散らばる。

### 2. 作業ツリーを確認する

`git status` で現在のブランチと未コミットの変更を確かめる。

- 未コミットの変更があれば、新しいブランチに持ち込むか（`git switch -c` はそのまま持ち込む）、先にコミット・stash するかをユーザーに確認する。持ち込むと、別の作業の変更が新しいブランチの最初のコミットに混ざる
- すでに作業用のブランチにいて、依頼がその続きなら、新しいブランチは作らない。独立してレビューできる別の作業なら、新しいブランチを提案する

### 3. ベースブランチを決める

これらのプロジェクトのブランチの流れは 2 つある。どちらかはリポジトリに `develop` があるかで決まる:

| 流れ | 長命ブランチ | 作業用のブランチの切り元・PR の向き先 |
| --- | --- | --- |
| GitHub Flow | `main` | `main` |
| 簡略版の Git Flow | `main`（本番）・`develop`（開発・ステージング） | `develop`。`develop` → `main` はリリース PR だけで、`release/*`・`hotfix/*` は使わない |

推測で `main` を決め打ちしない。次の順で確認する:

1. `AGENTS.md` / `CLAUDE.md` に書かれた運用（例: 機能のブランチは `develop` から切り、`develop` → `main` はリリース PR だけ）
2. リモートの長命ブランチ: `git ls-remote --heads origin develop main`。`develop` があれば簡略版の Git Flow なので、作業用のブランチは `develop` から切る。本番の不具合を急いで直す場合も同じで、`main` から直接切らない。`main` から切ると、`develop` にまだ無いリリース前の差分を巻き込むか、逆にリリース済みの変更が欠けた状態で始まる
3. デフォルトブランチ: `git symbolic-ref refs/remotes/origin/HEAD`（無ければ `git remote show origin` の HEAD branch）

先行の PR に重ねる場合は、先行の PR のブランチがベースになる（`../create-pr/rules/split-and-stack.md`）。決まらない場合は、ユーザーに確認する。

### 4. 名前を決める

`rules/naming.md` に従って名前を作り、同名のブランチが無いことを確かめる:

```bash
git branch --list <name>
git ls-remote --heads origin <name>
```

どちらかにあれば、既存のブランチを使い回さず、名前を変えるかユーザーに確認する。マージ済みの古いブランチに新しい作業を積むと、PR に古い差分が混ざる。

### 5. 最新のベースを取得する

```bash
git fetch origin "+refs/heads/<base>:refs/remotes/origin/<base>"
```

refspec を省いた `git fetch origin <base>` は使わない。`--single-branch` で clone したリポジトリでは `FETCH_HEAD` しか更新されず、`origin/<base>` が作られないか古いまま残り、次の手順が失敗するか古い地点から切ってしまう。

### 6. 作成する

まず、ベースにまだ無いコミットが手元にあるかを確かめる:

```bash
git log --oneline origin/<base>..HEAD
```

- **空のとき**（新しい作業を始める）: 最新のベースから作る

  ```bash
  git switch --no-track -c <name> origin/<base>
  ```

  手元の `<base>` ではなく `origin/<base>` から切るのは、手元のブランチは古いことが多く、古い地点から切ると PR の時点でコンフリクトするため。`--no-track` を付けるのは、`origin/<base>` から切ると上流が `<base>` に設定され、`push.default` の設定次第では、引数なしの `git push` がベースブランチへ向かうため。上流は初回の push で `git push -u origin <name>` として設定する

- **コミットがあるとき**（長命ブランチの上ですでにコミットした作業を PR にする、など）: それがこのブランチに入れる作業かをユーザーに確認し、入れるなら現在の HEAD から作る

  ```bash
  git switch -c <name>
  ```

  `origin/<base>` から切ると、そのコミットは手元の `<base>` に残ったまま新しいブランチに入らず、PR の差分が空になる。手元の `<base>` は `origin/<base>` より進んだまま残るので、そのことも伝える。`git reset` で戻すかはユーザーに任せ、勝手に戻さない（push 前のコミットは戻すと失われうる）

### 7. 報告する

作ったブランチ名・切り元（`origin/<base>` か現在の HEAD か、とそのコミット SHA）・持ち込んだコミットと未コミットの変更の有無を伝える。push は依頼されたときだけ行い、PR の作成は `create-pr` に引き継ぐ。

## 拡張ガイド（将来の作業者向け）

- プロジェクト固有の命名（チケット番号を含める、など）は本スキルに書かず、そのプロジェクトの `AGENTS.md` / `CLAUDE.md` に書く。本スキルは手順 3・4 でそれを優先する
- 命名に観点を足すときは、まず `rules/naming.md` への追記で済まないか検討する。ファイルを増やしたら「参照ファイルの選択」の表にも行を足す
- push・PR の作成・ブランチの削除まで面倒を見るなら、本スキルに足さず `create-pr` か別のスキルに置く（本スキルは「作成」で完結させる）
