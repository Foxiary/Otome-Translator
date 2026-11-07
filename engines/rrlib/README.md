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

   ```
   python tools/nsp.py romfs "<game>.nsp" jp "spec_win/ssdata/ttlm_nam.*"
   python tools/sprite.py export jp/spec_win/ssdata/ttlm_nam.memfs anh_menu
   ```

   Thư mục `anh_menu/` có:
   - `mat_ttlm.png`: cả tấm ảnh 4096×4096, để xem tổng thể;
   - `mat_ttlm/<tên ô>.png`: mỗi ô một file, tên lấy theo phần hình dùng nó. Ví dụ `mat_ttlm_com01_off.png` / `_on.png` là chữ 新しく始める lúc chưa chọn / đang chọn, `mat_ttlm_com01_setu.png` là câu chú thích dọc của nó, `mat_nam_bodoru_txt.png` là 戻る;
   - `cells.csv`: vị trí và kích thước từng ô.

   Vẽ lại ô cần dịch bằng phần mềm sửa ảnh bất kỳ (Photoshop, GIMP, Krita…), **giữ nguyên kích thước và tên file**, nền trong suốt vẫn trong suốt. Muốn sửa thẳng trên ảnh lớn cũng được; nếu sửa cả hai thì ô nhỏ được dán sau nên đè lên. Rồi chạy thử, sau đó ghi:

   ```
   python tools/sprite.py import jp/spec_win/ssdata/ttlm_nam.memfs anh_menu --out <thư mục mod>/romfs/spec_win/ssdata
   python tools/sprite.py import jp/spec_win/ssdata/ttlm_nam.memfs anh_menu --out <thư mục mod>/romfs/spec_win/ssdata --apply
   ```

   Công cụ chỉ dán những ô khác bản game. Nó báo ô sai kích thước, file đặt sai tên, và ô nào đè lên ô khác. Bản dựng được tự kiểm: file không sửa phải giữ nguyên từng byte, ảnh đã sửa phải đúng từng điểm ảnh. Chữ vẽ ra ngoài khung ô sẽ không hiện, vì game chỉ cắt đúng khung đó.

7. **Đóng gói** giống zip gốc: `exefs/` và `romfs/` nằm ngay ở gốc file zip.

## Những điều cần nhớ

- **Đừng chép nguyên tag JP vào bản dịch.** `patch.py` và `sheetfix.py` đã xử lý bốn trường hợp:
  - Câu JP dùng nhiều `#P` để tự ngắt dòng: gộp lại thành một khối.
  - Bản dịch dài hơn JP: đẩy `y` xuống để các câu không đè nhau.
  - Cách dòng mỗi màn hình mỗi khác: 60px hoặc ~75px.
  - 27 câu JP cố tình đặt ở y=1200, ra ngoài màn hình, vì chữ đã vẽ sẵn trong tranh (bài thơ ở cảnh mở đầu): bản Việt phải **để không có tag**, nếu không chữ dịch chỉ còn trong backlog.
- **Không đọc memfs một mình để kết luận game nạp file nào.** Bản patch 02/10 có sửa `exefs/main` để chuyển hướng 3 file mở đầu sang bản tiếng Việt nối ở cuối membody (`exehook.py` đọc ra được). `patch.py` trỏ thẳng các mục đó và tránh trùng cặp mà exe chuyển hướng.
- **Nới mục memfs sang 32-bit thì được, sửa tại chỗ thì không.** Phải ghi lại toàn bộ RSON (`rson.py` làm việc này). Sửa vài byte tại chỗ làm lệch offset, game không nạp được kịch bản nào và đen màn hình.

## Giới hạn

- Không tạo hay sửa font (`romfs/spec_win/font/*.font.memfs`): `applysheet.py` cần font của một bản mod có sẵn. Chữ hoa nào bản mod chưa từng dùng (lần này là `Ể`, `Ổ`, mỗi chữ một lần) thì ghi bằng chữ thường và báo lại.
- `#T` và `#KW` bị mất phải sửa tay theo cột JP; công cụ chỉ liệt kê.
- `sprite.py` chỉ ghi được ảnh RGBA8 thường. Mọi ảnh chữ giao diện của game đều thuộc loại này. Nền nén khối (BC), như 5 ảnh nền `mat_ttlm_bg_chr0N` của menu tiêu đề, và các mặt nạ chuyển cảnh 8/16/24-bit thì được liệt kê rồi bỏ qua. Công cụ không tự vẽ chữ: người dịch tự vẽ lại từng ô.
- Chỉ mới thử với Matsurika no Kei. Game khác dùng `rrlib/memfs` có thể cần chỉnh lại các số đo trong `tools/tags.py`.

`tools/README.md` liệt kê từng công cụ và kết quả đã kiểm trên dữ liệu thật.
