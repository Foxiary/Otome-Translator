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
| `patch.py` | | Dựng lại `script.memfs` + `script.membody`: trả `#P`, trỏ thẳng chunk, nới u32, sửa header, tự kiểm |
| `sheetfix.py` | | Từ sheet dịch (`.xlsx`) ra file đề xuất sửa tag theo đúng tab + dòng |
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

**Đã thử trong game:** EV00_0001_01 với `#P` đã trả, và memfs có mục 32-bit.
**Chưa thử lại trong game:** việc bỏ tag cho các câu ngoài màn hình, và 3 cảnh mở
đầu được trỏ thẳng bằng mục 32-bit.

## Quy ước

- Lệnh ghi file thì chạy thử trước; thêm `--apply` mới ghi. File đã có giữ thành `.bak`.
- Mọi đường dẫn nhận qua tham số; không có gì gắn cứng với máy nào.
- Comment trong code bằng tiếng Anh, tài liệu bằng tiếng Việt, `CLAUDE.md` bằng tiếng Anh.
