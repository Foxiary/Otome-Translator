# Cách dùng Otome Translator

Đây là hướng dẫn cho cửa sổ app. Bạn chọn một công cụ, điền biểu mẫu, rồi bấm **Chạy công cụ**. Không cần gõ lệnh của engine.

## Bắt đầu với game

Màn hình đầu hỏi game bạn đang dịch.

Thả file `.nsp` hoặc `.xci` vào cửa sổ, hoặc chọn file đó. App đọc tên các file bên trong rồi chọn engine:

- **Otomate**, cho game Otomate và Idea Factory: gói `.cpk`, kịch bản STCM2L, font `.ffu`.
- **Unity**, cho game Unity: bundle và `.assets`, font TextMeshPro, code IL2CPP.
- **rrlib**, cho Matsurika no Kei -kEi- Tenmei Iniden: `script.memfs` và kịch bản `.tat`.

Nếu đã biết engine, mở **Tự chọn engine** và chọn. Danh sách đó cũng cho xem mọi công cụ của engine.

## Thư mục dự án

Dự án là một thư mục trên máy. Trong đó có file game gốc, bản mod trong một thư mục riêng (`romfs` và `exefs`, sẵn để chia sẻ), và bộ công cụ của engine.

- **Bắt đầu từ đầu** giải nén toàn bộ game vào một thư mục mới.
- **Tiếp tục bản mod có sẵn** chép bản mod vào thư mục mod của dự án mới, kèm game gốc bên cạnh.
- **Mở dự án đã có** dùng thư mục dự án bạn đã tạo trước đây.

Không có file `.nsp` hay `.xci` thì giải nén bằng Ryujinx. Chuột phải vào game, chọn **Extract Data → RomFS**, rồi chọn một thư mục trống. Chữ nằm trong file chương trình thì giải nén thêm **ExeFS**. Khi Ryujinx báo xong, chọn thư mục đó ở đây.

Lấy file từ `.nsp` hoặc `.xci` cần `prod.keys`. App tìm ở các chỗ quen thuộc, kể cả thư mục system của Ryujinx. File cập nhật không phải bản game gốc; hãy chọn bản gốc.

App không kèm file game, font, bản dịch hay khóa Nintendo. App chép script của engine vào dự án, và giữ nguyên file bạn đã sửa.

**Thư mục dự án** trên thanh bên là dự án đang mở. **Mở thư mục** hiện nó trong trình quản lý file. **Đổi** chọn thư mục khác. Mỗi engine nhớ một thư mục riêng.

## Python

Các công cụ cần thư viện Python. Mở **Cài đặt**, bánh răng ở cuối thanh bên, rồi chọn **Môi trường Python**.

Nếu còn thiếu gói, chọn **Cài các gói**. Việc này cần mạng và mất vài phút. Nhật ký chạy hiện tiến trình. Chấm đỏ trên bánh răng nghĩa là bước này vẫn còn.

Bạn cũng có thể trỏ app tới một Python đã cài sẵn các gói đó.

## Chạy một công cụ

Thanh bên liệt kê **nhóm công cụ** của engine đang chọn. Mở một nhóm, rồi chọn công cụ. Ô tìm kiếm tìm trong mọi công cụ của engine đó.

Trang công cụ nói nó làm gì. Điền biểu mẫu. Đường dẫn có thể là đường dẫn đầy đủ, hoặc tính từ thư mục dự án. Dấu trên nhãn cho biết ô nào không có thì không chạy được.

**Chạy công cụ** bắt đầu. **Dừng** thì ngắt. Nhật ký phía dưới là những gì công cụ in ra. Một lúc chỉ chạy một công cụ, và phải chạy xong mới đổi engine.

Kéo mép phải của thanh bên khi tên bị cắt.

## Vá bản dịch

**Vá thoại** (Otomate) và **Vá chữ game** (Unity) là đường ngắn của bước ghi cuối. Đó không phải cả quy trình dịch. Bảng phải được tạo, gộp và kiểm tra trước. Các bước của từng engine nằm ở dưới. **Tùy chỉnh nâng cao** được gấp lại. **Chạy thử**, bên trong đó, chỉ báo những gì sẽ đổi.

## Đo khung chữ

Với Otomate, **Đo khung chữ** nằm cạnh các nhóm. Bước kiểm tra độ rộng dùng nó để biết khung rộng bao nhiêu.

Chọn ảnh chụp trong game lúc đang hiện một câu dài, sau khi đã cài font tiếng Việt. Gõ đúng câu đó như trên màn hình, từ chữ đầu tới chữ cuối. Bấm điểm đầu câu, điểm cuối câu, và mép khung. Độ phân giải của ảnh không quan trọng.

Câu thoại không bị giới hạn theo số byte. Thứ giới hạn câu là bề rộng khung. Hãy canh theo backlog, vì mọi câu thoại đều được chiếu lại ở đó. **Tìm câu quá dài** đo bằng font của lần **Vá giao diện** gần nhất, nên hãy chạy bước đó trước khi tin danh sách. Đo bằng font sẽ đưa vào game, không phải font gốc.

## Cài đặt và ngôn ngữ

Bánh răng mở **Cài đặt**:

- **Môi trường Python**
- **Kiểm tra cập nhật**. App chỉ báo khi có bản mới. App không tự tải hay tự cài bản đó.
- **Giao diện tối**

Quả địa cầu cạnh bánh răng đổi app sang tiếng Anh hoặc tiếng Việt. Việc này đổi chữ của chính app, không đổi sổ tính hay bản dịch trong đó.

Biểu tượng sách mở hướng dẫn này. Biểu tượng thông tin xem lại hướng dẫn ngắn.

## Otomate: ba nhánh tách riêng

Thoại, giao diện và file chương trình không phụ thuộc nhau. Nhánh nào xong thì đóng nhánh đó vào mod. Giữ một bản `.cpk` chạy được trước mỗi lần thay. **Kiểm tra file kịch bản** có thể sạch mà game vẫn treo: kiểm tra sạch không có nghĩa là game chạy.

### Thoại, STORY.cpk

1. **Bảng dịch → Tạo bảng dịch.** Bước này đọc thoại và menu vào một sổ tính. Không đổi thứ tự cột. Tiếng Anh ở cột B, tiếng Việt ở cột C. Công cụ tìm hai cột đó theo vị trí. Tiếng Nhật ở cột D.
2. Dịch cột C. Ô chỉ có khoảng trắng và `#n` là dòng đệm, không phải câu cần dịch.
3. Khi nhóm dịch gửi bảng về, chạy lại **Tạo bảng dịch** với file đó ở chỗ gộp, và tích **Relink**. Cột ID của bảng dịch theo bản Nhật bước qua mọi ô tiếng Anh để trống, nên các dòng phía sau rơi sai chỗ. Relink bỏ cột đó và khớp lại từ bản Nhật với bản Anh. **Khớp lại bảng với game** là chính bước khớp đó, chạy riêng.
4. Dịch câu đang nằm trong game bạn vá. Cột tiếng Nhật lấy từ cartridge cũ không khớp bản Anh làm từ bản cập nhật sau. Chỗ hai bên khác nhau thì theo game.
5. **Tìm câu chưa dịch** liệt kê câu game còn chưa có bản dịch, kể cả câu bảng không có dòng nào, kèm chỗ cần chèn và cả khung thoại. Hãy đọc cả khung. Chữ Anh của một ô hay là câu Nhật của ô bên cạnh, vì hai bản ngắt dòng khác nhau. Muốn chèn dòng thì cột A để trống được, còn ô tiếng Nhật phải chép từ game, không gõ lại.
6. **Xuất nhãn chương**, dịch các tiền tố ngắn đó, rồi **Điền tên chương**. Làm sau khi gộp và trước khi ghi thoại. Tên chương đã điền là dữ liệu suy ra: gộp lại là mất, chạy lại **Điền tên chương** là có. Excel cắt dấu cách ở cuối ô; công cụ lấy lại dấu cách đó từ bản gốc.
7. **Tìm mã lệnh bị lỗi** mỗi khi nhận bảng mới. Lệnh gõ sai, như thẻ màu thiếu dấu đóng, sẽ bị ghi vào game nếu bỏ bước này. Bước ghi chỉ đếm lệnh viết đúng.
8. Với dòng giao diện, không sửa tiếng Anh ở cột B, kể cả lỗi chính tả. Chữ Anh đó là cách công cụ tìm đúng ô. Trong thoại, `#Color` và `#NAME` được chuyển sang dòng khác của cùng một phiên bản. Không được chuyển sang phiên bản khác. `#n` được bỏ, không được thêm.
9. **Vá thoại.** Chọn bảng đã xong và một thư mục cho kết quả. App chép bảng, điền tên chương, kiểm tra, rồi ghi kịch bản vào thư mục đó. Bảng bạn chọn và file game ban đầu không bị sửa. Mở **Tùy chỉnh nâng cao** để chạy thử.
10. **File game → Đóng gói lại CPK.** Đưa `STORY.cpk` gốc, một tên file mới, và thư mục vừa vá. Mọi file khác trong gói giữ nguyên. File mới lớn hơn nhiều, vì file thay vào không được nén. Chép file đó vào `romfs` của mod.

### Giao diện, SYSTEM.cpk

Font và chữ giao diện đi chung một file, nên đóng gói một lần.

1. **Font → Tạo font game**, bắt đầu từ một file `.ffu` gốc của game. Xem kết quả ở cỡ game vẽ, không phải cỡ của file. Khe một hai hàng giữa dấu thanh và dấu mũ biến mất trên màn hình và chữ trông như bị cắt. Ô nâng dấu là thứ mở khe đó ra lại.
2. **Giao diện → Vá giao diện**, có chọn bảng dịch. Bước này ghi menu, Options và Glossary rồi đóng `SYSTEM.cpk`. Đừng chạy không có bảng rồi trông chờ một lần ghi menu riêng còn lại: không có bảng thì nó giữ nguyên file dữ liệu đang có. **Bản dịch Glossary mẫu** chỉ để xem font. Nó thay chữ Glossary thật bằng vài câu mẫu.
3. Không sửa cột B của các dòng giao diện. Dòng menu được dùng số lần xuống dòng khác bản gốc. `#NAME`, `#Color` và `#PosX` phải giữ.
4. Chép `SYSTEM.cpk` vào `romfs` của mod. Trên Windows, **Install** trong **Vá giao diện** có thể chép giúp vào Ryujinx.

### File chương trình

Màn hình chính hiện một câu trích của ending vừa phá. Các câu đó không nằm trong file nén nào.

1. **File chương trình → Lấy file chương trình của game**, rồi **Giải nén file chương trình**, rồi **Tạo bảng dịch từ file chương trình**.
2. Ngắt dòng của các câu này là ngắt dòng thật, không phải `#n`.
3. **Ghi bản dịch vào file chương trình.** Câu dài hơn được phép cho tới khi hết chỗ trống. Công cụ từ chối chứ không cắt câu. Kết quả nằm ở `exefs`, không phải `romfs`.

## Unity

Làm trên bản sao. Giữ một bản dump không bao giờ sửa. Công cụ nào ghi file đều chạy thử trước: nếu không có lỗi, app cho biết sẽ ghi vào đâu và hỏi bạn có ghi không. Riêng công cụ đóng gói vẫn chờ bạn tích **Build**. Ghi đè lên chính file đã mở thì giữ một bản `.bak`.

1. **Lấy dữ liệu → Giải nén dữ liệu game** cho phần dữ liệu, và **Lấy file chương trình của game** khi cần chữ nằm trong code. RomFS của file cập nhật không đọc được; dùng bản game gốc.
2. **Xem → Xem bên trong file.** Chữ thường nằm ở TextAsset, khung TextMeshPro, chuỗi nướng trong code, hoặc pixel vẽ sẵn trên tranh. Chưa có công cụ chung cho chữ vẽ sẵn trên tranh.
3. **Chữ → Xuất chữ ra bảng dịch.** Sổ tính có mã, câu gốc, và cột Translation để trống. Dịch cột đó. Danh sách lựa chọn nằm dạng chữ trong chữ thì tích **Nested** lúc xuất. Bước ghi từ chối dòng có câu gốc không còn khớp file.
4. **Vá chữ game** ghi bảng trở lại. Sửa nhỏ thì dùng **Nhập lại file chữ đã sửa** hoặc **Thay một từ**.
5. **Khung chữ → Tìm khung chữ**, rồi **Chỉnh khung chữ**: kích thước, xuống dòng, và tự thu nhỏ. Bước này không đổi chỗ game tự ngắt dòng trong code. Trường hợp đó cần **Tạo bản vá code**.
6. **Font → Kiểm tra font thiếu chữ.** Font tự vẽ chữ mới từ file thì đổi bằng **Thay font**; thay mọi bản sao của font đó. Font có chữ đã vẽ sẵn vào atlas thì chạy **Thử bộ vẽ chữ** một lần, rồi **Thêm chữ vào font**. Thêm chữ chỉ dùng chỗ trống của atlas. Atlas đầy thì phải dựng lại trong Unity Editor.
7. **Code game → Tìm chữ trong code game**, rồi **Sửa chữ trong code game**. Chữ mới không được dài hơn chữ cũ, và chữ có dấu chiếm nhiều chỗ hơn. **Tạo bản vá code** dành cho sửa mã máy. Để cả hai cho tới khi quả thật có câu nằm trong code.
8. **Phát hành → Đóng gói bản phát hành.** Chỉ in kế hoạch cho tới khi tích **Build**. File zip dùng cho Ryujinx và Atmosphere.

## rrlib, Matsurika no Kei

Kịch bản không nằm trong CPK. Nó là `common/script.memfs` cùng `common/script.membody`. Đừng giải nén cả game: gần như toàn bộ là voice. Các công cụ có trong app. Hãy thử bản dựng trong game trước khi chia sẻ. Font trong `romfs/spec_win/font` không được xử lý.

1. **Lấy dữ liệu → Lấy file ra khỏi game**, với đường dẫn `common/script.memfs` và `common/script.membody`. Rồi chạy **Lấy file chương trình của game**. Giữ bản Nhật này. Bản patch sau chuyển hướng ba kịch bản mở đầu từ file chương trình, nên chỉ nhìn mục lục thì không biết game đang nạp byte nào.
2. **Bản patch → Kiểm tra bản patch**, so với bản Nhật đó. Nó báo tag vị trí, tên và dừng bị mất, câu bị giấu ngoài màn hình, và độ dài sai. Không sửa gì.
3. **Bản patch → Dựng lại bản patch.** Lần chạy thử in báo cáo; đồng ý khi app hỏi thì nó ghi `script.memfs` và `script.membody`. Rồi chép hai file đó vào `romfs/common/` của mod. Đừng chép tag `#P` của tiếng Nhật lên câu tiếng Việt. Nhiều tag trong một câu Nhật thường là một đoạn. Bản dịch dài hơn thì được đẩy xuống để các câu không đè nhau. Hai mươi bảy câu Nhật cố ý nằm ngoài màn hình, vì chữ đã vẽ trên tranh: những câu đó để không có tag vị trí, nếu không bản dịch biến mất và chỉ backlog còn giữ. Tag `#T` và `#KW` bị mất được liệt kê để sửa tay.
4. **Bảng dịch → Danh sách sửa tag cho bảng dịch.** Chép các câu đề xuất vào cột bản dịch. Bảng cũng nói câu nào phải để không có tag. Sửa bảng để lần dựng sau không mất tag nữa.
5. Đóng gói mod như file zip gốc: `exefs/` và `romfs/` nằm ngay ở gốc, không nằm trong một thư mục nữa.

Thư mục dự án còn có ghi chú riêng của engine, như `README.md` và `DICH.md`. Đó là ghi chú về script và định dạng file. Hướng dẫn này là hướng dẫn cho app.
