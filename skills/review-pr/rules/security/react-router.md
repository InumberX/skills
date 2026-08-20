# セキュリティ観点: React Router

対象: React Router v7 / v8 の framework mode。v6 以前と library mode は未検証。

一般原則は `boundary.md` にある。ここではその具体化だけを書くので、両方読んだときは指摘を片方にまとめる。

## 先に `react-router.config.*` の `ssr` を確認する

同じ `loader` でも、設定次第で「リクエスト時に動く公開エンドポイント」と「ビルド時にしか動かないコード」に分かれる。**フレームワーク名だけで判断すると結論が反転する。**

| 設定 | `loader` / `action` の実行時期 | 主な論点 |
| --- | --- | --- |
| `ssr: true`（設定ファイルが無い場合の既定値） | リクエスト時にサーバー | 1〜4（公開エンドポイントとしての扱い） |
| `ssr: false` + `prerender` | ビルド時のみ | 5（バンドルと生成済み HTML への埋め込み） |

`react-router.config.*` は省略可能で、無ければ `ssr: true` として扱われる。**ファイルが無いことを「SSR ではない」と読み違えない。**

## 1. `loader` / `action` は URL を持つ公開エンドポイント

single fetch により、ルートのデータは `<ルートのパス>.data` として直接リクエストできる。**画面を経由せずデータ取得関数だけを叩けるため、コンポーネント側や親ルート側の条件分岐は認可にならない。** 認可は各 `loader` / `action` の内部に置く。

差分での見つけ方: 新しい `loader` / `action` が追加されたとき、その関数自身が権限を検証しているか。「このルートは管理画面の下にあるから安全」は成立しない。

## 2. `loader` の戻り値はルート単位でクライアントへ配られる

`boundary.md` の「描画しなくても配られる」の具体形。single fetch は**そのリクエストに関わる全ルートの `loader` の戻り値をまとめて返す**ため、子ルートが使わない親レイアウトの戻り値もクライアントに届く。

差分での見つけ方: `loader` が API 応答を丸ごと返していないか。特に共通レイアウトの `loader` は全ページで配布されるので、絞り込みの有無を優先して見る。

## 3. middleware は前段のフィルタとして扱う

v8 では middleware が既定で有効（v7 では `future.v8_middleware`）。ここに認可をまとめると、迂回されたとき全ルートが同時に破られる。middleware は共通処理の置き場として使い、**保護対象の `loader` / `action` 側にも検証を残す**。

サーバーで動く `middleware` とブラウザで動く `clientMiddleware` は別物で、**後者は信頼境界にならない**。差分でどちらのエクスポートが追加されたかを名前で確認する。

## 4. `redirect()` のリダイレクト先を利用者入力から組み立てない

クエリパラメータやフォーム値をそのまま `redirect()` に渡すと、外部サイトへ誘導するオープンリダイレクトになる。**遷移先を文字列として検査せず、同一オリジンに解決できるかで判定する。**

```ts
// Bad: 任意の絶対 URL へ飛ばせる
return redirect(new URL(request.url).searchParams.get('redirectTo') ?? '/')

// Bad: 文字列の前方一致による検査。`/\evil.com` を通してしまう
const to = new URL(request.url).searchParams.get('redirectTo') ?? '/'
return redirect(to.startsWith('/') && !to.startsWith('//') ? to : '/')

// Good: 自サイトのオリジンに解決できるものだけ許可する
const url = new URL(request.url)
const to = new URL(url.searchParams.get('redirectTo') ?? '/', url.origin)
return redirect(to.origin === url.origin ? to.pathname + to.search : '/')
```

前方一致の検査が不足するのは、**URL パーサとブラウザが `\` を `/` と同一視する**ため。`/\evil.com` はスラッシュ1つで始まるので `startsWith('//')` の除外をすり抜けるが、解決すると `https://evil.com` になる。`\\evil.com` や `////evil.com` も同様。オリジンで比較すればこれらはまとめて弾ける（`javascript:` スキームもオリジンが一致しないため落ちる）。

`action` を追加したときは、POST を受ける以上 Origin 検証や CSRF トークンの経路に載っているかも確認する。

## 5. `ssr: false` のときは「認可」ではなく「埋め込み」を見る

SPA モードでは `loader` は prerender 時にしか動かないため、`loader` に対する認可の論点は成立しない。代わりに次の2点を見る。

- **ビルド時に取得した値が、生成済み HTML とバンドルに焼き付いて全閲覧者へ配られる。** `prerender` の対象ルートが増えたとき、その `loader` が閲覧者非依存の内容だけを返しているか。認証付き API から取得した値をここで解決していないか
- **実行時のデータ取得は `clientLoader` が担い、ブラウザで動く。** 呼び出し先の API キーや認証情報はバンドルに含まれる前提で見る。サーバー側でしか使えない資格情報を `clientLoader` へ移していないか
