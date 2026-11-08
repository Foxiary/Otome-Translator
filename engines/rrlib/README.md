# Engine rrlib — Matsurika no Kei -kEi- Tenmei Iniden

Bộ công cụ cho bản Việt hóa **Matsurika no Kei -kEi- Tenmei Iniden**
(`0100EA001A626000`, bản JP 1.0.0). Game không dùng CPK/STCM2L như các game
Otomate khác. Kịch bản nằm trong cặp `romfs/common/script.memfs` (mục lục, định
dạng RSON mà file tự gọi là `rrlib/memfs`) và `script.membody` (130 file `.tat`
nén zlib, mã bytecode "KUV ").

Công cụ ra đời khi sửa bản patch Việt ngày 02/10/2026. Bản đó làm mất tag vị trí
`#P`, khiến hai câu dẫn hiện chồng vào một khung. Ghi chú định dạng chi tiết, kèm
các bẫy đã gặp, nằm ở `CLAUDE.md` (tiếng Anh).

Trong Otome Translator, thả file `.nsp` hoặc thư mục mod của game vào cửa sổ là app tự chuyển sang engine này và điền sẵn đường dẫn; mọi công cụ bên dưới đều có biểu mẫu trong app. Có thể chạy thẳng bằng dòng lệnh như dưới đây.

Chỉ cần Python 3. Riêng `sheetfix.py` và `applysheet.py` cần thêm openpyxl, `sprite.py` cần Pillow. `nsp.py` dùng
pycryptodome nếu có, không có thì gọi lệnh `openssl`. Repo không chứa dữ liệu game.

## Quy trình

1. **Lấy bản JP** (cần `prod.keys`, mặc định `~/.switch/prod.keys`). Trong app, "Lấy toàn bộ dữ liệu game" lấy cả RomFS lẫn ExeFS từ `.nsp` hoặc `.xci` (12 842 file, 5,8 GB, khoảng 16 giây); chỉ cần kịch bản thì bằng dòng lệnh:

   ```
   python tools/nsp.py romfs "<game>.nsp" jp "common/script.*"
   python tools/nsp.py exefs "<game>.nsp" jp/exefs
   ```

2. **Ghi bảng dịch vào game.** Tải sheet về dạng `.xlsx`, rồi chạy thử (không ghi file):

   ```
   python tools/applysheet.py --sheet sheet.xlsx --jp jp --mod <thư mục mod> --out out --report bao_cao.csv
   python tools/applysheet.py --sheet sheet.xlsx --jp jp --mod <thư mục mod> --out out --apply
   ```

   Cần sẵn một bản mod tiếng Việt, vì ba thứ lấy từ đó:
   - **font:** chữ có dấu nằm trên mã kana (`ệ` → `る`), và công cụ tự học cách mã hoá từ những câu bản mod đã có;
   - **các câu sheet không có dòng:** tên nhân vật, lựa chọn;
   - **`exefs/main`:** để biết exe chuyển hướng file nào.

   Mỗi ô được xử lý như builder cũ của nhóm dịch:
   - bỏ `「」『』“”` và đổi `"` thành `'` vì font không có các dấu này;
   - ngắt dòng ở 62 ký tự;
   - tag (`#P`, `#T`, `#KW`…) ghi **đúng như trong ô**. Có tag hay không là do người sửa bản dịch quyết định; công cụ không tự thêm hay bỏ tag nào. Kiểm tag bằng `audit.py` (bước 3) hoặc `sheetfix.py`.

   Ô nào không ghi được thì giữ câu của bản mod: câu còn sót kana (font dùng các ô kana cho chữ Việt nên sẽ hiện sai chữ), câu chưa dịch, hai dòng dịch khác nhau cho cùng một câu. File báo cáo ghi rõ tab, dòng và lý do. Thêm `--apply` thì ghi vào `out/`, rồi chép vào `romfs/common/` của mod.

3. **Kiểm bản patch** mà không sửa gì:

   ```
   python tools/audit.py --jp jp --patch <thư mục mod> --csv loi.csv
   ```

   Báo các lỗi: code khác JP, số chuỗi lệch, file đọc nhầm chunk, câu mất `#P` / `#T` / `#KW`, câu bị `#P` đẩy ra ngoài màn hình, trường độ dài code sai.

4. **Sửa bản patch.** Lệnh này chỉ chạy thử, in báo cáo, không ghi file:

   ```
   python tools/patch.py --jp jp --patch <thư mục mod> --out out --report sua.csv
   python tools/patch.py --jp jp --patch <thư mục mod> --out out --apply
   ```

   Thêm `--apply` thì mới ghi `script.memfs` và `script.membody` vào `out/`, rồi chép vào `romfs/common/` của mod. `patch.py` tự đọc `exefs/main` của mod nếu có, để biết exe chuyển hướng file nào.

5. **Sửa sheet dịch.** Tải sheet về dạng `.xlsx`, rồi:

   ```
   python tools/sheetfix.py --sheet sheet.xlsx --jp jp --out sua_tag.xlsx
   ```

   File ra có:
   - các câu đề xuất (đã trả `#P`) để chép vào cột `vi_text`;
   - danh sách câu **không** được thêm `#P`;
   - các câu mất `#T`/`#KW` cần sửa tay.

   Sửa sheet là để lần build sau không mất tag lại.

6. **Dịch chữ vẽ trong ảnh giao diện.** Chữ ở menu tiêu đề, nút bấm và câu chú thích (新しく始める, ロード, 戻る, セーブデータをロードします。…) không phải chuỗi chữ mà là ảnh, nên sheet dịch không có. Mỗi màn hình là một cặp `romfs/spec_win/ssdata/<tên>.memfs` + `.membody`: menu tiêu đề là `ttlm_nam`; các gói khác đặt tên theo màn hình (`opt` cài đặt, `log` backlog, `dialog` hộp thoại…).

   Trong app việc này có hai bước, nằm ở nhóm **Ảnh giao diện**:

   **Bước 1: "Lấy ảnh của một màn hình ra".** Chọn màn hình và một thư mục, tốt nhất là thư mục trống. Nếu thư mục đã có ảnh lấy ra từ trước, công cụ chưa ghi gì: app hỏi "Ghi đè ảnh trong thư mục này?" và nêu những ảnh khác ảnh gốc của game (thường là ô bạn đã vẽ lại). Giống Finder hay File Explorer, bạn chọn: **giữ ảnh đã sửa** (chỉ ghi lại phần còn lại), **thay bằng ảnh gốc**, hoặc **chọn từng ảnh** (mỗi ảnh một câu hỏi "Giữ hay thay?", có ô "Làm vậy với các ảnh còn lại"). Ảnh nào bị thay thì được chép sang `<tên>.png.bak` nằm cạnh nó trước. Bằng dòng lệnh thì thêm `--overwrite`, và `--keep <file>` cho từng ảnh muốn giữ. Bỏ trống thư mục thì chỉ xem danh sách các ô. Bằng dòng lệnh:

   ```
   python tools/nsp.py romfs "<game>.nsp" jp "spec_win/ssdata/ttlm_nam.*"
   python tools/sprite.py export jp/spec_win/ssdata/ttlm_nam.memfs anh_menu
   ```

   Thư mục `anh_menu/` có:
   - `mat_ttlm.png`: cả tấm ảnh 4096×4096, để xem tổng thể;
   - `mat_ttlm/<tên ô>.png`: mỗi ô một file, tên lấy theo phần hình dùng nó. Ví dụ `mat_ttlm_com01_off.png` / `_on.png` là chữ 新しく始める lúc chưa chọn / đang chọn, `mat_ttlm_com01_setu.png` là câu chú thích dọc của nó, `mat_nam_bodoru_txt.png` là 戻る;
   - `cells_ttlm_nam.csv`: vị trí và kích thước từng ô. Tên có kèm màn hình, nên nhiều màn hình dùng chung một thư mục cũng không đè nhau.

   Chạy xong, app hiện nút mở thư mục và nút **"Bước tiếp: Đưa ảnh đã vẽ lại vào game"**, đồng thời điền sẵn màn hình và thư mục này vào bước 2. Mở bước 2 mà các ô đó còn trống thì app cũng lấy từ lần chạy bước 1 gần nhất.

   **Vẽ lại** ô cần dịch bằng phần mềm sửa ảnh bất kỳ (Photoshop, GIMP, Krita…), **lưu đè lên đúng file đó, giữ nguyên tên file**, nền trong suốt vẫn trong suốt. Muốn sửa thẳng trên ảnh lớn cũng được; nếu sửa cả hai thì ô nhỏ được dán sau nên đè lên.

   Chữ Việt dài hơn ô thì **vẽ ảnh to hơn** cũng được (ví dụ ロード 178×52 thành "TẢI GAME" 276×72). Bước 2 tìm một chỗ trống trong cùng tấm ảnh lớn, đặt ô vào đó và cho game cắt ô ở chỗ mới. Game vẽ mỗi ô quanh tâm của nó, nên chữ nở đều sang hai bên, tâm vẫn ở chỗ chữ Nhật cũ. Vì vị trí không đổi, ô sát mép màn hình mà vẽ to quá thì có thể tràn ra ngoài: 戻る ở góc phải trên menu tiêu đề nên giữ cỡ cũ. Ô nào có chuyển động chưa rõ cách vẽ (không chỉ xoay, phóng to thu nhỏ, mờ dần quanh tâm) thì công cụ từ chối đổi cỡ và báo phải vẽ đúng cỡ cũ. Công cụ cũng báo khi tấm ảnh lớn không còn chỗ trống.

   **Bước 2: "Đưa ảnh đã vẽ lại vào game".** Chọn thêm thư mục Ghi vào: `romfs/spec_win/ssdata` trong mod. Lần chạy đầu là chạy thử; không lỗi thì app hỏi có ghi không. Bằng dòng lệnh:

   ```
   python tools/sprite.py import jp/spec_win/ssdata/ttlm_nam.memfs anh_menu --out <thư mục mod>/romfs/spec_win/ssdata
   python tools/sprite.py import jp/spec_win/ssdata/ttlm_nam.memfs anh_menu --out <thư mục mod>/romfs/spec_win/ssdata --apply
   ```

   Thư mục ảnh không phải do bước 1 tạo cho đúng màn hình đó thì bị từ chối. Chưa vẽ lại ô nào thì công cụ báo vậy và không ghi gì. Nếu thư mục Ghi vào đã có file của màn hình đó, lần chạy thử nêu tên chúng và hộp hỏi của app ghi rõ "sẽ bị thay". Trước khi ghi, mỗi file cũ được chép sang `<tên>.bak` nằm ngay cạnh nó, trong chính thư mục Ghi vào, ví dụ `ttl.memfs` → `ttl.memfs.bak`. Nếu `.bak` đã có từ lần trước thì thành `.bak2`, `.bak3`…, nên không bản sao nào bị đè. Hộp hỏi và nhật ký đều ghi đúng tên bản sao. (`sprite.py translate` làm một trong hai bước tuỳ thư mục, cho ai quen chạy một lệnh.)

   Công cụ chỉ dán những ô khác bản game. Nó báo ô nào được đổi cỡ (cỡ mới, chỗ mới, số trạng thái trỏ sang), file đặt sai tên, và ô nào đè lên ô khác. Bản dựng được tự kiểm: file không sửa phải giữ nguyên từng byte, ảnh đã sửa phải đúng từng điểm ảnh, và file `.ssdata` chỉ được đổi khung x/y/w/h của các ô đã dời. Chữ vẽ ra ngoài khung ô sẽ không hiện, vì game chỉ cắt đúng khung đó. Luôn chọn màn hình gốc của game (bản lấy ra ở bước 1), không chọn bản đã dựng trong mod.

7. **Dịch chữ nằm trong file chương trình.** Câu hỏi trong hộp thoại (`前回と同じ名前を使用します｡` + `よろしいですか？` khi đặt tên), thông báo lưu nhanh/tải nhanh, câu hỏi ở màn hình cài đặt, chú thích nút (`{B} 戻る`), mục từ điển và tên chương không nằm trong kịch bản mà nằm sẵn trong `exefs/main`. Sheet dịch không có dòng nào cho chúng, và bản patch 02/10 chưa dịch câu nào. Vì font Việt dùng các ô kana cho chữ có dấu, những câu đó hiện thành chữ sai (`と` → `Ề`, `を` → `ặ`, `よ` → `Ở`).

   Trong app việc này nằm ở nhóm **File chương trình**, hai bước:

   **Bước 1: "Lấy chữ trong file chương trình ra".** Chọn `exefs/main` của mod và nơi lưu danh sách (`.csv`). Danh sách có khoảng 780 dòng, cột `address`, `refs`, `jp_text`, `vi_text`, `note`. Đưa file vào Google Sheets (File → Nhập), dịch cột `vi_text`, rồi tải về lại dạng `.csv` (File → Tải xuống → CSV, tải đúng tab đó). Bằng dòng lệnh:

   ```
   python tools/exetext.py export <thư mục mod>/exefs/main chu_exe.csv
   ```

   Cột `note` ghi những gì phải giữ: `%d`, `%ls` (thiếu hay thừa là game có thể lỗi, nên công cụ từ chối câu đó), ký hiệu nút `{B}`, `￥ｎ` (xuống dòng). Một số dòng là thông báo lỗi dành cho lập trình viên (biến, tag, UV…), không cần dịch. Ô `vi_text` để trống thì câu đó giữ tiếng Nhật.

   **Bước 2: "Ghi chữ vào file chương trình".** Cần thêm **bảng mã font** (`.json`): lưu bằng "Ghi bảng dịch vào game", điền ô Map (`applysheet.py --map font.json`). Ô Ghi vào là `exefs` trong mod. Lần chạy đầu là chạy thử; không lỗi thì app hỏi có ghi không, và file `main` cũ được chép sang `main.bak`. Bằng dòng lệnh:

   ```
   python tools/exetext.py import <thư mục mod>/exefs/main chu_exe.csv --map font.json --out <thư mục mod>/exefs --report bao_cao_exe.csv
   python tools/exetext.py import <thư mục mod>/exefs/main chu_exe.csv --map font.json --out <thư mục mod>/exefs --apply
   ```

   Câu dịch dài hơn tiếng Nhật cũng được: công cụ không ghi đè chỗ cũ mà đặt câu dịch vào một vùng mới ở cuối file chương trình, rồi trỏ mọi chỗ đang dùng câu tiếng Nhật sang đó. Muốn sửa bản dịch thì cứ chạy lại trên chính file `main` đã ghi: lần nào công cụ cũng gỡ bản dịch cũ, dựng lại từ bản gốc. Ba đoạn chuyển hướng của bản patch 02/10 được giữ nguyên. Kết quả được tự kiểm, nhưng câu nào chương trình tạo ra theo cách khác thì vẫn là tiếng Nhật, và khung chữ không tự rộng ra, nên hãy thử từng màn hình trong game. File `main` mới khoảng 7 MB (bản cũ 3 MB) vì được ghi không nén; game vẫn nạp bình thường.

8. **Đổi font.** Font nằm ở `romfs/spec_win/font`: `standard` (gothic tròn), `extra` (gothic đậm), `extra2` (viết tay), `extra3` (có chân), `ui`, mỗi cái kèm một bản `_outline` là viền vẽ bên dưới chữ. Bốn lựa chọn フォント 一 二 三 四 ở màn hình cài đặt lần lượt là `standard`, `extra`, `extra2`, `extra3` (二 = `extra` đã thấy trên màn hình; ba cái kia suy từ thứ tự trong file chương trình). `ui` không nằm trong bốn lựa chọn đó. Tool "Tạo font tiếng Việt" (`font.py gen`) vẽ lại chữ ASCII và chữ tiếng Việt từ file `.ttf`/`.otf` bạn chọn, tự chỉnh cỡ cho chữ H cao bằng chữ của game, rồi dựng luôn bản viền. Kana và kanji giữ nguyên. Font phải có đủ chữ tiếng Việt; muốn mỗi font một kiểu thì điền thêm các ô Font cho standard / extra / extra2 / extra3 / ui.

   Kịch bản hiện tại viết chữ Việt bằng mã kana (`ệ` → `る`), nên cần **bảng mã font** (ô Map, lưu bằng "Ghi bảng dịch vào game"): mỗi chữ được vẽ vào đúng ô kana đó, kịch bản không phải dựng lại. Chữ nào bảng mã chưa có (`Ể`, `Ổ`, các chữ hoa bản mod chưa dùng) được thêm ô với mã riêng; điền ô Lưu bảng mã để lần sau "Ghi bảng dịch vào game" (ô Use map) và "Ghi chữ vào file chương trình" (ô Map) ghi đúng các chữ đó. Template là thư mục font của bản **tiếng Nhật**, Ghi vào là `romfs/spec_win/font` trong mod. Bằng dòng lệnh:

   ```
   python tools/font.py gen --template <JP>/romfs/spec_win/font --out <thư mục mod>/romfs/spec_win/font \
       --font MyFont-Regular.ttf --map font.json --map-out font-moi.json
   python tools/font.py gen ... --apply
   python tools/font.py preview <thư mục mod>/romfs/spec_win/font/standard.font.memfs "Xin chào, Ể Ổ ặ" thu.png \
       --outline <thư mục mod>/romfs/spec_win/font/standard_outline.font.memfs --map font-moi.json
   ```

   Lần chạy thử in cỡ chữ, độ dày viền đo được và **độ rộng trung bình một chữ so với font gốc**: rộng hơn khoảng 8% trở lên thì câu dài (ngắt ở 62 ký tự) có thể tràn khung, nên chọn font hẹp hơn hoặc giảm cỡ (ô Cỡ chữ). "Xem trước font" vẽ thử một dòng ra ảnh. Chưa thử font dựng bằng công cụ này trong game: hãy xem thoại, menu, và các chữ hoa mới thêm.

   Không dùng Map thì chữ Việt được thêm với mã Unicode thật và kana giữ nguyên, nên chữ Nhật còn sót trong file chương trình sẽ hiện đúng tiếng Nhật. Nhưng khi đó **mọi** câu tiếng Việt phải dựng lại bằng Unicode, kể cả tên nhân vật và lựa chọn mà sheet không có — các công cụ chưa làm việc đó, nên hiện giờ hãy dùng Map.

9. **Đóng gói** giống zip gốc: `exefs/` và `romfs/` nằm ngay ở gốc file zip.

## Những điều cần nhớ

- **Đừng chép nguyên tag JP vào bản dịch.** `patch.py` và `sheetfix.py` đã xử lý bốn trường hợp:
  - Câu JP dùng nhiều `#P` để tự ngắt dòng: gộp lại thành một khối.
  - Bản dịch dài hơn JP: đẩy `y` xuống để các câu không đè nhau.
  - Cách dòng mỗi màn hình mỗi khác: 60px hoặc ~75px.
  - 27 câu JP cố tình đặt ở y=1200, ra ngoài màn hình, vì chữ đã vẽ sẵn trong tranh (bài thơ ở cảnh mở đầu): bản Việt phải **để không có tag**, nếu không chữ dịch chỉ còn trong backlog.
- **Không đọc memfs một mình để kết luận game nạp file nào.** Bản patch 02/10 có sửa `exefs/main` để chuyển hướng 3 file mở đầu sang bản tiếng Việt nối ở cuối membody (`exehook.py` đọc ra được). `patch.py` trỏ thẳng các mục đó và tránh trùng cặp mà exe chuyển hướng.
- **Nới mục memfs sang 32-bit thì được, sửa tại chỗ thì không.** Phải ghi lại toàn bộ RSON (`rson.py` làm việc này). Sửa vài byte tại chỗ làm lệch offset, game không nạp được kịch bản nào và đen màn hình.

## Giới hạn

- `applysheet.py` học bảng mã font từ một bản mod có sẵn. Chữ hoa nào bản mod chưa từng dùng (lần này là `Ể`, `Ổ`, mỗi chữ một lần) thì ghi bằng chữ thường và báo lại — trừ khi font được dựng lại bằng `font.py gen --map-out` và bảng mã mới được đưa vào `--use-map`.
- `#T` và `#KW` bị mất phải sửa tay theo cột JP; công cụ chỉ liệt kê.
- `exetext.py` chỉ dịch được câu mà nó tìm thấy chỗ trỏ tới (con trỏ trong bảng relocation, hoặc lệnh ADRP+ADD/ADR). Exe JP có 7 chuỗi không tìm thấy, đều là dữ liệu nhị phân trông giống chữ.
- `sprite.py` chỉ ghi được ảnh RGBA8 thường. Mọi ảnh chữ giao diện của game đều thuộc loại này. Nền nén khối (BC), như 5 ảnh nền `mat_ttlm_bg_chr0N` của menu tiêu đề, và các mặt nạ chuyển cảnh 8/16/24-bit thì được liệt kê rồi bỏ qua. Công cụ không tự vẽ chữ: người dịch tự vẽ lại từng ô.
- Chỉ mới thử với Matsurika no Kei. Game khác dùng `rrlib/memfs` có thể cần chỉnh lại các số đo trong `tools/tags.py`.

`tools/README.md` liệt kê từng công cụ và kết quả đã kiểm trên dữ liệu thật.
