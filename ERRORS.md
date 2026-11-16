# ERRORS — 試錯紀錄

某個做法嘗試超過 2 次才成功時，在此記錄。

## 範本

### YYYY-MM-DD 〈任務名稱〉
- **沒用的做法**：
- **有用的做法**：
- **下次要記得**：

### 2026-11-16 mac-health-check：Finder 背景模式導覽與刪除
- **沒用的做法**：背景模式用「前往檔案夾」對話框輸入路徑後按 Return 或 Esc（兩者都送不出，對話框卡住，要按關閉鈕兩次）；第一次「移到垃圾桶」後直接再按 File → Move to Trash（垃圾桶視窗變成主視窗，選單只剩 Put Back）；使用者停在全螢幕 App 時點選 Finder 列（被拒，視窗也移不過來）。
- **有用的做法**：Go 選單固定項目（Library）＋展開三角形＋排序＋捲動；點列的日期欄位選取；zoom 核對路徑列；回 Library 視窗重新點一次目標列後再按 File → Move to Trash；全螢幕時請使用者切回一般桌面或自己動手。
- **下次要記得**：已寫進 mac-health-check 的「背景操作的已知限制」與 C4。

### 2026-11-16 mac-health-check：殘留判定誤判
- **沒用的做法**：只靠 App 清冊判斷擁有者是否已移除——把仍在使用的 AutoCAD 2026（裝在應用程式下兩層）與中華電信憑證元件（裝在 `~/Library`）列成殘留，使用者追問才發現。
- **有用的做法**：`computer_list_apps` 用廠商關鍵字或 bundle id 片段查（不限安裝位置）；`computer_resolve_access` 回 `notInstalled` 時再看 `didYouMean`。
- **下次要記得**：清冊上沒有只是線索，列清單前每一組都要用系統查一次。
