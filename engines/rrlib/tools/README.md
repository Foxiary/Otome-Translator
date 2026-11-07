# Công cụ của engine rrlib

Mỗi script tự mô tả trong docstring đầu file (`python tools/<tên>.py -h`).
Định dạng file nằm ở `../CLAUDE.md`.

| script | lệnh | việc |
|---|---|---|
| `nsp.py` | `romfs`, `exefs` | Lấy từng file ra khỏi NSP bằng `prod.keys`, không bung cả RomFS |
| `rson.py` | `dump`, `check` | Đọc/ghi `script.memfs` (RSON); `check` = đọc rồi ghi lại phải giống từng byte |
| `memfs.py` | `list`, `unpack`, `check` | Mục lục + `script.membody`: chunk nào được nạp, chunk thừa, bung ra `.tat` |
| `kuv.py` | `strings`, `calls`, `check` | Kịch bản `.tat`: liệt kê chuỗi, xem lệnh gọi (`GuideMess`, `KW`, `WinClear`…), dựng lại |
| `exehook.py` | | Đọc các cặp (offset, size) mà `exefs/main` đã vá chuyển hướng |
| `audit.py` | | Kiểm bản patch so với JP: code, số chuỗi, tag bị mất, tag đẩy chữ ra ngoài màn hình |
| `applysheet.py` | | Ghi sheet dịch (`.xlsx`) vào `script.memfs` + `script.membody`: ngắt dòng, mã hoá theo font của mod, trả `#P`, tự kiểm |
| `patch.py` | | Dựng lại `script.memfs` + `script.membody`: trả `#P`, trỏ thẳng chunk, nới u32, sửa header, tự kiểm |
| `sheetfix.py` | | Từ sheet dịch (`.xlsx`) ra file đề xuất sửa tag theo đúng tab + dòng |
| `sprite.py` | `translate`, `export`, `import`, `check` | Ảnh giao diện (`spec_win/ssdata/*.memfs`). `translate`: thư mục trống thì xuất từng ô chữ ra PNG theo tên phần hình, thư mục đã xuất thì dán các ô đã vẽ lại, đóng gói, tự kiểm. `export` / `import` là từng nửa riêng. Cần Pillow |
| `tags.py` | | Thư viện: đọc tag, trả `#P`, các số đo màn hình — không phải lệnh |

## Đã kiểm trên dữ liệu thật

Chạy trên NSP JP 1.0.0 và bản patch Việt ngày 02/10/2026:

- `nsp.py romfs` lấy ra `script.memfs` và `script.membody` giống bản trích bằng
  cách khác. `nsp.py exefs` ra `main` của JP.
- `rson.py check`: memfs JP và memfs VI đều đọc rồi ghi lại giống từng byte.
- `kuv.py check`: cả 128 file `.tat` đều dựng lại được. Chỉ 10 file khác ở
  trường độ dài code, vì bản patch cũ ghi sai trường này.
- `exehook.py`: exe JP không có chuyển hướng; exe của patch có đúng 3 cặp.
- `audit.py` trên bản patch 02/10 báo:
  - 1273 câu mất `#P`, 140 câu mất `#T`, 33 câu mất `#KW`;
  - 6 câu bị `#P` giấu ra ngoài màn hình;
  - 10 header sai độ dài code;
  - 3 file được exe chuyển hướng.

  Trên bản đã sửa thì chỉ còn `#T`/`#KW`.
- `patch.py` cho ra **giống từng byte** bản đã cài và chơi thử trong Astrid,
  trong 3,6 giây.
- `sheetfix.py` trên sheet tải ngày 05/11/2026 ra file giống từng ô với file
  đề xuất đã gửi người dịch: 1279 câu `#P`, 27 câu không thêm tag, 138 `#T`, 31 `#KW`.

- `applysheet.py` trên sheet tải ngày 07/11/2026 và bản mod đang cài, trong 11 giây:
  - học được 68 chữ của font từ chính bản mod;
  - ghi 30 470 chuỗi vào 124 kịch bản. Bỏ qua 145 ô còn sót kana, 1 ô chưa dịch
    và 103 dòng trùng câu nhưng dịch khác; các câu đó giữ chữ của bản mod;
  - tự kiểm OK (cấu trúc); tag ghi đúng như sheet;
  - `audit.py` trên bản dựng báo đúng những gì sheet đang có: 27 câu giữ
    `#P(…,1200)` nên bị giấu (các bài thơ, EV00_0000 dòng 48–69…) và 4 câu
    thiếu `#P` (EV06_0009_01 dòng 26, 30, 31, 32). Sửa trong sheet rồi dựng lại;
  - so với bản đang chơi: 65 845 chuỗi không đổi, 5 169 chuỗi đổi chữ theo sheet
    mới, 485 chuỗi chỉ đổi cách xuống dòng (các biến thể `#T` giờ mỗi cái một dòng
    như JP), 41 chuỗi chỉ khác tag. Không chuỗi đã dịch nào quay về tiếng Nhật;
  - ở những dòng mà chữ trong sheet vẫn giống bản 02/10, cách chuyển chữ cho ra
    giống từng byte 93,6% chuỗi của bản đó. Phần còn lại lệch vì builder cũ làm
    mất `#P`/`#KW` và gộp các đoạn có tag thành một dòng.

- `sprite.py check` trên cả 51 gói ảnh dưới `spec_win` (48 gói `ssdata` cùng `image/boot`, `image/transition`, `image/ui`):
  - gói nào dựng lại không sửa cũng giống từng byte;
  - đọc được 1 689 ô, ô nào cũng nằm gọn trong ảnh của nó;
  - 612 / 737 ảnh là RGBA8, nén lại rồi giải nén ra đúng dữ liệu cũ. 125 ảnh còn lại là nền nén khối và mặt nạ chuyển cảnh, công cụ bỏ qua.

  Lần chạy này lộ một lỗi của `rson.py`: nó căn mảng u16 theo 4 byte, còn game căn theo 2. Ở `script.memfs` hai cách tình cờ cho cùng kết quả. Đã sửa; memfs JP, bản cài và hai bản dựng trước vẫn đọc rồi ghi lại giống từng byte.
- `sprite.py export` + `import` trên `ttlm_nam` (menu tiêu đề): sửa một ô thì đúng khung ô đó đổi điểm ảnh. Các file khác của gói giữ nguyên từng byte, chỉ vị trí trong memfs dời theo.

**Đã thử trong game:** EV00_0001_01 với `#P` đã trả, và memfs có mục 32-bit. Menu tiêu đề `ttlm_nam` do `sprite.py import` dựng (07/11/2026, Astrid): 17 ô vẽ lại bằng chữ Việt (5 mục lúc chưa chọn và đang chọn, 5 câu chú thích dọc, 戻る, おまけ) hiện đúng.
**Chưa thử trong game:** bản do `applysheet.py` dựng.
**Chưa thử lại trong game:** việc bỏ tag cho các câu ngoài màn hình, và 3 cảnh mở
đầu được trỏ thẳng bằng mục 32-bit.

## Quy ước

- Lệnh ghi file thì chạy thử trước; thêm `--apply` mới ghi. File đã có được chép sang `<tên>.bak` nằm cạnh nó trong cùng thư mục (đã có `.bak` thì `.bak2`, `.bak3`…); lần chạy thử và nhật ký ghi đúng tên bản sao.
- Mọi đường dẫn nhận qua tham số; không có gì gắn cứng với máy nào.
- Comment trong code bằng tiếng Anh, tài liệu bằng tiếng Việt, `CLAUDE.md` bằng tiếng Anh.
