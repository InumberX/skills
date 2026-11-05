# 開閉する UI（アコーディオン・全文表示・折りたたみ）

差分に、押すと領域が開いたり閉じたりするボタンが追加・変更された場合に読む。観点の根拠は HTML と WAI-ARIA の仕様だけで、特定のフレームワークに依存しない。コード例は React（TSX）で示すが、ほかのフレームワークでも同じ属性を付ける。

## ネイティブの `details` / `summary` で足りるなら、ARIA は要らない

開閉を `<details>` と `<summary>` で作っている場合、開閉の状態はブラウザが支援技術に伝える。ARIA 属性が無いことを指摘しない。以下は、`button` 要素と独自の状態で開閉を作っている場合の観点である。

## 開閉の状態を `aria-expanded` で伝える

開閉するボタンには `aria-expanded` を付け、開いているとき `true`、閉じているとき `false` にする。見た目（矢印の向き、「閉じる」の文言）だけでは、スクリーンリーダーの利用者に状態が伝わらない。文言を「全文を表示」「閉じる」と切り替えても、それが開閉の状態であることは伝わらない。

```tsx
// Bad — 状態が文言とアイコンにしか無い
<button type="button" onClick={toggle}>
  {isOpen ? '閉じる' : '全文を表示'}
</button>
```

```tsx
// Good — 状態を属性で伝える
<button type="button" aria-expanded={isOpen} onClick={toggle}>
  {isOpen ? '閉じる' : '全文を表示'}
</button>
```

## `aria-controls` は任意。付けるなら、指す先を常に DOM に残す

`aria-controls` は、ボタンと開閉する領域の関係を伝える属性である。WAI-ARIA Authoring Practices の Disclosure パターンでは任意とされ、支援技術の対応も限られる。付けていないことは指摘しない。

付ける場合は、指す先の要素が**閉じている間も DOM にある**ことを確かめる。閉じている間は領域を描画しない実装に `aria-controls` を付けると、ボタンが存在しない `id` を指す。閉じている間は `hidden` 属性で隠して DOM に残すか、`aria-controls` を外すよう指摘する。

```tsx
// Good — 閉じている間も領域を DOM に残し、hidden で隠す
<button type="button" aria-expanded={isOpen} aria-controls={bodyId} onClick={toggle}>…</button>
<div id={bodyId} hidden={!isOpen}>…</div>
```

一部を常に見せて残りを開閉する（全文表示のように、閉じている間も冒頭を見せる）場合は、領域は常に DOM にあるので、そのまま `aria-controls` で指してよい。

## 確かめること

- **共通のボタン部品を経由している場合**、その部品が `aria-expanded`（付けるなら `aria-controls` も）を受け取って、描画先の要素に渡しているかを確かめる。部品が受け取らないと、呼び出し側で指定しても描画されない。部品に足す場合は、既にある ARIA 属性と同じ形で、同じ描画先に渡す
- **`id` が一意か。** 一覧の各項目に開閉がある場合、固定の文字列を使うと `id` が重複する。フレームワークの一意な ID を生成する仕組み（React の `useId` など）か、項目のキーから作る
- **ボタンが `button` 要素か。** `div` や `span` にクリック処理を付けただけでは、キーボードで操作できず、ボタンとしても読み上げられない。フォームの中に置く場合は `type="button"` を指定する（指定しないと送信ボタンになる）

## 指摘の重要度

`aria-expanded` が無いことは、見た目では気づけないため Should で挙げる。`aria-controls` が無いことは指摘しない。存在しない `id` を指していることは Nit で挙げる。プロジェクトの `rules/` にアクセシビリティの方針（対応レベルなど）があれば、そちらの重要度に従う。
