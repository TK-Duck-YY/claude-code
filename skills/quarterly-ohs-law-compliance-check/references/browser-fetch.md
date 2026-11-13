# 瀏覽器抓取操作（law.moj.gov.tw）

## 目錄
- 通用規則
- §1 抓日期＋法規名稱
- §2 pcode 驗證與重新解析
- §3 抓沿革
- §4 抓條文
- 待實測事項

---

## 通用規則

- **一律使用內建瀏覽器**（桌面版「Browse with Claude」，偏好瀏覽器設為內建瀏覽器）。
  **不使用 claude-in-chrome。**
- 沙箱 `curl` 對 law.moj.gov.tw 會回 403，**不要嘗試**；改在內建瀏覽器頁內用同源 `fetch`。
- 做法：先在內建瀏覽器開啟任一 law.moj.gov.tw 頁面（例如首頁），再於該頁內執行 JS，
  這樣 `fetch('/LawClass/...')` 才是同源請求。
- 並發建議 4～6 條。單次執行時間過長時，改成「發射後輪詢」：把結果存進 `window._done`／`window._m`，
  再分次讀取，不要在一次呼叫裡等到全部跑完。
- 子代理（步驟 7）各自使用內建瀏覽器並在結束時關閉自己開的頁面；子代理只產出 JSON、不碰 Excel。

---

## §1 抓日期＋法規名稱

名稱是驗證關鍵，日期與名稱要一起抓。

```js
var html = await (await fetch('/LawClass/LawAll.aspx?pcode=' + pcode)).text();
var doc  = new DOMParser().parseFromString(html, 'text/html');
var pairs = {};
doc.querySelectorAll('tr').forEach(tr => {
  var th = tr.querySelector('th'), td = tr.querySelector('td');
  if (th && td) pairs[th.innerText.replace(/[\s：:]/g, '')] = td.innerText.trim();
});
var actual = (pairs['法規名稱'] || '').replace(/\s+/g, ' ').replace(/ EN$/, '').trim();
var pubKey = ['修正日期','發布日期','公布日期','制定日期','訂定日期'].find(k => pairs[k]);
// 民國 114 年 12 月 23 日 → 114.12.23
```

## §2 pcode 驗證與重新解析

`actual !== 預期法規名稱` 者，用站內搜尋重新解析 pcode：

```js
var html = await (await fetch('/Law/LawSearchResult.aspx?ty=ONEBAR&kw=' + encodeURIComponent(name))).text();
// 取 href 含 pcode= 的連結，找「名稱完全相符」者
```

解析出新 pcode 後，**重抓一次日期並再驗一次名稱**，全部通過才進下一步。

## §3 抓沿革

```js
var html = await (await fetch('/LawClass/LawHistory.aspx?pcode=' + pcode)).text();
var doc  = new DOMParser().parseFromString(html, 'text/html');
var d = doc.querySelector('.law-reg-content.law-history') || doc.querySelector('.law-reg-content');
var t = (d ? d.innerText : '').replace(/\r/g, '');
var i = t.indexOf('歷史條文');            // 最新一則在「歷史條文」之前
var before = i > 0 ? t.slice(0, i) : t;
var latest = before.slice(before.lastIndexOf('中華民國')).trim().replace(/\n\s*/g, '');
```

沿革文字的解析規則（修正／增訂／刪除／全文修正／施行日期）見 SKILL.md 步驟 4。

## §4 抓條文（換行結構是重點）

```js
window.getArts = async function (pcode) {
  var html = await (await fetch('/LawClass/LawAll.aspx?pcode=' + pcode)).text();
  var doc  = new DOMParser().parseFromString(html, 'text/html');
  var map  = {};
  doc.querySelectorAll('.row').forEach(r => {
    var no = r.querySelector('.col-no'), da = r.querySelector('.col-data');
    if (!no || !da) return;
    var m = no.textContent.trim().match(/第\s*([\d\-之]+)\s*條/);
    if (!m) return;
    // 必須逐行取；innerText 在 DOMParser 文件會退化成 textContent，換行全失
    var lines = [...da.querySelectorAll('div[class^="line-"]')]
                  .filter(d => !d.querySelector('div[class^="line-"]'));
    map[m[1].replace('之', '-')] = lines.length
      ? lines.map(d => d.textContent.trim()).filter(Boolean).join('\n')
      : da.textContent.trim();
  });
  window._m = map;
  return Object.keys(map).length;
};
```

**驗證**：凡條文同時含「一、」與「二、」者，值必須含 `\n`；每條長度要與內建瀏覽器端記錄一致（截斷是無聲的）。

---

## 待實測事項（內建瀏覽器，尚未驗證）

以下項目改用內建瀏覽器後**尚未實跑確認**。首次實跑時請逐項確認，
有差異就直接改本檔並補進 `ERRORS.md`：

1. 能否在頁內執行 JS 並取得回傳值（`fetch`、`DOMParser`）
2. 單次執行有無逾時上限（舊實測值 45 秒，僅供參考）
3. 能否同時開多個頁面（影響步驟 7 的子代理並發）
4. `window._done`／`window._m` 是否能跨呼叫保留
