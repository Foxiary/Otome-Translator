// Vietnamese text for the tool catalogs, shown when the interface language is
// Vietnamese. Tool ids match catalog-otomate.js and catalog-unity.js; anything
// missing here falls back to the English in those files.
const DRY = 'Chạy thử trước; nếu không có lỗi, app hỏi bạn có ghi thật không. Nếu lưu đè lên file gốc, app giữ một bản sao lưu .bak.';

const tools = {
  'build': {title: 'Vá giao diện', description: 'Tạo bản vá giao diện hoàn chỉnh: vẽ font tiếng Việt, đưa bản dịch menu từ bảng dịch vào, rồi đóng gói tất cả thành file SYSTEM.cpk.', note: 'Tùy chọn Install chép kết quả vào Ryujinx và chỉ chạy trên Windows.'},
  'ffugen': {title: 'Tạo font cho game', description: 'Chuyển một font thông thường (TTF hoặc OTF) sang định dạng font riêng của game (.ffu) và thêm chữ tiếng Việt. Cần một file .ffu gốc của game làm mẫu.', note: 'Đặt sai kích thước hoặc dùng font lỗi có thể làm game bị treo. Luôn thử font mới trong game.'},
  'ffu-inspect': {title: 'Kiểm tra font game', description: 'Cho biết font game (.ffu) có bao nhiêu chữ và kích thước ra sao. Gõ thử vài chữ để xem font có vẽ được không.'},

  'cpk-list': {title: 'Xem danh sách file trong CPK', description: 'Liệt kê mọi file nằm trong một file nén của game (.cpk), kèm dung lượng. Không thay đổi gì.'},
  'cpk-unpack': {title: 'Giải nén CPK', description: 'Chép các file trong file nén của game (.cpk) ra một thư mục. Gõ một phần tên file để chỉ lấy file khớp, hoặc để trống để lấy hết.'},
  'cpk-repack': {title: 'Đóng gói lại CPK', description: 'Tạo bản sao mới của file nén game (.cpk), trong đó các file được thay bằng file cùng tên trong thư mục của bạn. Các file khác giữ nguyên.', note: 'File mới lớn hơn bản gốc nhiều vì các file thay vào không được nén. Đây là chuyện bình thường.'},
  'gbnl': {title: 'Kiểm tra file dữ liệu menu', description: 'Mở một file dữ liệu menu hoặc từ điển của game (.gbin hoặc .gstr), cho xem cấu trúc và kiểm tra app có dựng lại đúng y file đó không. Dùng khi nghi file bị hỏng.'},
  'stcm2l': {title: 'Kiểm tra file kịch bản', description: 'Kiểm tra một file kịch bản (.DAT), hoặc cả thư mục kịch bản, có đọc và dựng lại được mà không hỏng không. Tích All khi chọn thư mục.'},
  'tid-list': {title: 'Xem danh sách hình ảnh', description: 'Liệt kê hình ảnh của game (.tid) kèm kích thước, từ file CPK, thư mục hoặc một file ảnh.'},
  'tid-unpack': {title: 'Xuất hình ảnh ra PNG', description: 'Lưu hình ảnh của game (.tid) thành ảnh PNG thường để mở xem. Hữu ích khi tìm chữ được vẽ thẳng vào ảnh, như menu ở màn hình chính.', note: 'App chưa đưa được ảnh đã sửa trở lại vào game.'},

  'mksheet': {title: 'Tạo bảng dịch', description: 'Chép toàn bộ chữ trong game (thoại và menu) ra một file Excel để dịch. Cũng có thể lấy bản dịch có sẵn đưa vào file mới.', note: 'Không đổi thứ tự cột: tiếng Anh ở cột B, tiếng Việt ở cột C. Khi gộp bảng từ nhóm dịch gửi về, hãy tích Relink.'},
  'checksheet': {title: 'Kiểm tra bảng dịch', description: 'Kiểm tra bảng dịch có được làm cho đúng phiên bản game bạn đang có không. Gần 100% là khớp; thấp là nếu ghi vào sẽ làm hỏng kịch bản.'},
  'glossary': {title: 'Tạo bảng dịch từ điển', description: 'Chép phần Glossary trong game (thuật ngữ và lời giải thích) ra file Excel, kèm tiếng Nhật bên cạnh nếu bạn có bản game tiếng Nhật.'},
  'trbatch-prefill': {title: 'Điền sẵn bản dịch', description: 'Tự điền tên nhân vật, và nếu muốn cả những câu giống y hệt, từ một bản dịch bạn đã có. Giúp người dịch khỏi làm lại việc cũ.'},
  'trbatch-export': {title: 'Chia bảng cho người dịch', description: 'Lấy các dòng chưa dịch và chia thành nhiều file nhỏ để giao cho người dịch.'},
  'trbatch-import': {title: 'Gộp bản dịch đã xong', description: 'Đưa phần đã dịch xong của người dịch trở lại bảng chính.'},
  'trbatch-status': {title: 'Tiến độ dịch', description: 'Đếm số dòng đã dịch và số dòng còn lại.'},
  'filltitles-prefixes': {title: 'Xuất nhãn chương', description: 'Tạo một bảng nhỏ gồm các nhãn chương (như "Act 1:" hay "Chapter 2:") còn cần dịch. Nhiều nhãn đã có gợi ý sẵn.'},
  'filltitles-fill': {title: 'Điền tên chương', description: 'Ghép tên chương hoàn chỉnh vào bảng làm việc, dùng các nhãn đã dịch. Chạy sau khi gộp bảng mới và trước khi ghi thoại vào game.'},
  'relinkjp': {title: 'Khớp lại bảng với game', description: 'Tìm lại xem mỗi dòng của bảng dịch (dịch theo bản Nhật) thuộc về câu nào trong game, bằng cách so bản Nhật với bản Anh. Khi gộp bảng mà tích Relink thì bước này đã được làm sẵn.'},
  'chuadich': {title: 'Tìm câu chưa dịch', description: 'Liệt kê các câu trong game còn chưa có bản dịch, kể cả câu mà bảng của nhóm dịch không có dòng nào, kèm vị trí cần chèn và cả khung thoại xung quanh.', note: 'Đọc STORY.cpk ở gốc thư mục dự án, và tự tìm STORY.cpk bản Nhật ở bất kỳ đâu trong thư mục đó.'},
  'quarong': {title: 'Tìm câu quá dài', description: 'Liệt kê các câu đã dịch bị tràn ra ngoài khung chữ trong game, kèm gợi ý chỗ xuống dòng.', note: 'Đo bằng font của lần Build gần nhất, nên hãy chạy Vá giao diện trước. Nếu thêm bảng của nhóm dịch thì đọc cả STORY.cpk bản Nhật.'},
  'exportvar': {title: 'Tìm mã lệnh bị lỗi', description: 'Trong các câu bị từ chối khi ghi thoại, lọc ra những câu có mã lệnh (như #Color hay #NAME) thật sự bị hỏng, để người dịch chỉ phải sửa những chỗ cần sửa. Nên chạy mỗi khi nhận bảng mới.'},
  'reflow': {title: 'Ngắt dòng lại trong khung thoại', description: 'Chia lại bản dịch của mỗi khung thoại vào các dòng cho vừa font mà không mất chữ nào. Sửa các câu bị lệch một dòng.'},

  'applystory': {title: 'Ghi thoại theo câu tiếng Anh', description: 'Cách cũ để đưa thoại vào, dành cho bảng dịch không có mã dòng. Tìm từng câu theo chữ tiếng Anh.'},
  'portjp2us': {title: 'Chuyển bản dịch theo bản Nhật', description: 'Dành cho bảng dịch làm theo game bản Nhật: tìm vị trí tương ứng trong kịch bản của game bản Anh và ghi bản dịch vào đó.'},
  'applyui': {title: 'Ghi bản dịch giao diện vào game', description: 'Ghi bản dịch menu, Options và Glossary từ bảng dịch vào file dữ liệu của game, và có thể đóng gói luôn SYSTEM.cpk mới. Vá giao diện khi có chọn bảng dịch sẽ tự làm bước này.', note: 'Không sửa chữ tiếng Anh ở cột B của các dòng giao diện, kể cả lỗi chính tả: app dùng nó để tìm đúng chỗ.'},
  'translate-glossary': {title: 'Bản dịch mẫu cho Glossary', description: 'Đưa vài câu dịch mẫu vào màn Glossary để xem font hiển thị ra sao trong game. Không dùng cho bản dịch thật.', note: 'Bước này ghi đè bản dịch thật bằng câu mẫu.'},

  'exefs-extract': {title: 'Lấy file chương trình của game', description: 'Chép file chương trình (ExeFS) ra từ file game (.nsp hoặc .xci). Chỉ cần khi dịch các câu trích ở màn hình chính.', note: 'Cần file prod.keys đặt ở vị trí quen thuộc.'},
  'exefs-segments': {title: 'Giải nén file chương trình', description: 'Giải nén file chương trình chính (main) thành từng phần để đọc được chữ bên trong.'},
  'exefs-strings': {title: 'Tìm chữ trong file chương trình', description: 'Liệt kê chữ tìm thấy trong một phần đã giải nén của file chương trình. Có thể lọc theo từ khóa.'},
  'exefs-sheet': {title: 'Tạo bảng dịch từ file chương trình', description: 'Đưa chữ tìm thấy trong file chương trình ra file Excel để dịch, ví dụ các câu trích ở màn hình chính.'},
  'applyexe': {title: 'Ghi bản dịch vào file chương trình', description: 'Ghi chữ đã dịch vào file chương trình của game, có thể cài luôn vào Ryujinx. Câu dịch dài hơn bản gốc vẫn được.'},
  'textwidth': {title: 'Đo độ rộng chữ', description: 'Đo độ rộng các câu gốc của game với font của game, để biết mỗi khung chữ có bao nhiêu chỗ.'},

  'unity-exefs': {title: 'Lấy file chương trình của game', description: 'Chép file chương trình (main) ra từ file game hoặc file cập nhật (.nsp), để sau này vá chữ trong code.'},
  'unity-romfs': {title: 'Giải nén dữ liệu game', description: 'Chép toàn bộ file dữ liệu ra từ file game hoặc DLC (.nsp). Đây là những file bạn sẽ dịch.', note: 'Không hỗ trợ file cập nhật; hãy dùng bản game gốc.'},
  'unity-nso': {title: 'Giải nén file chương trình', description: 'Giải nén file chương trình (main) thành một file thường, cần khi tạo bản vá code.'},
  'unity-ls': {title: 'Xem bên trong file', description: 'Liệt kê nội dung của một file dữ liệu Unity (bundle hoặc .assets): chữ, font, hình ảnh… Không thay đổi gì.'},
  'unity-text-dump': {title: 'Xuất file chữ', description: 'Lưu từng đoạn chữ trong file Unity thành file .txt trong một thư mục, giữ nguyên như gốc, để bạn chỉnh sửa.'},
  'unity-text-import': {title: 'Nhập lại file chữ đã sửa', description: 'Đưa các file .txt đã sửa trở lại vào file Unity. File nào không sửa thì giữ nguyên.', note: 'Nếu chữ ở dạng JSON, đừng làm hỏng dấu ngoặc và dấu nháy. ' + DRY},
  'unity-text-replace': {title: 'Thay một từ', description: 'Thay một từ hoặc cụm từ bằng chữ khác trong một đoạn chữ, để sửa nhanh mà không cần bảng dịch.', note: DRY},
  'unity-sheet-export': {title: 'Xuất chữ ra bảng dịch', description: 'Chép chữ của game ra file Excel gồm mã, câu gốc và cột Translation để trống.'},
  'unity-tmp-list': {title: 'Tìm khung chữ', description: 'Liệt kê các khung chữ trên màn hình kèm kích thước, cỡ chữ và cách xuống dòng, để tìm khung quá nhỏ.'},
  'unity-tmp-set': {title: 'Chỉnh khung chữ', description: 'Chỉnh một khung chữ: kích thước, vị trí, cỡ chữ, tự thu nhỏ, xuống dòng và khoảng cách. Dùng mã lấy từ Tìm khung chữ.', note: DRY},
  'unity-tmpfont-info': {title: 'Kiểm tra font thiếu chữ', description: 'Liệt kê các font chữ của game và những chữ font còn thiếu, ví dụ chữ tiếng Việt.'},
  'unity-tmpfont-verify': {title: 'Thử bộ vẽ chữ', description: 'Vẽ lại vài chữ font đã có rồi so với bản gốc. Chạy một lần cho mỗi game trước khi dùng Thêm chữ vào font.'},
  'unity-tmpfont-add': {title: 'Thêm chữ vào font', description: 'Vẽ thêm những chữ còn thiếu, như chữ tiếng Việt, vào font không tự vẽ được chữ mới.', note: 'Chạy Thử bộ vẽ chữ với font này trước. ' + DRY},
  'unity-font-list': {title: 'Xem danh sách font', description: 'Liệt kê các font trong file Unity và số chữ mỗi font có.'},
  'unity-font-extract': {title: 'Lưu font ra file', description: 'Lưu một font của game ra file .ttf thông thường.'},
  'unity-font-replace': {title: 'Thay font', description: 'Thay một font trong game bằng file font .ttf khác. Chữ dùng font đó cũng đổi theo.', note: 'Một font thường có nhiều bản sao ở các file khác nhau; hãy thay hết. ' + DRY},
  'unity-font-coverage': {title: 'Kiểm tra chữ của font', description: 'Cho biết font .ttf không vẽ được những chữ nào, theo một ngôn ngữ, đoạn chữ bạn gõ, hoặc bản dịch trong bảng.'},
  'unity-il2cpp-find': {title: 'Tìm chữ trong code game', description: 'Tìm chữ nằm sẵn trong code của game (global-metadata.dat).'},
  'unity-il2cpp-patch': {title: 'Sửa chữ trong code game', description: 'Thay một đoạn chữ trong code của game. Chữ mới không được dài hơn chữ cũ, và chữ có dấu chiếm nhiều chỗ hơn chữ không dấu.', note: 'Thay đổi chỉ dùng được cho đúng phiên bản game này. ' + DRY},
  'unity-ips32': {title: 'Tạo bản vá code', description: 'Tạo file vá code (.ips) từ danh sách thay đổi, kiểm tra từng thay đổi với game trước. Dành cho người dùng nâng cao.', note: 'Địa chỉ là RVA, không phải cột Offset trong dump.cs. ' + DRY},
  'unity-release': {title: 'Đóng gói bản phát hành', description: 'Nén bản mod hoàn chỉnh thành file zip để người chơi cài vào Ryujinx hoặc Switch đã mod (Atmosphere).', note: 'Chỉ hiện kế hoạch cho tới khi bạn tích Build.'},

  'rrlib-extract': {title: 'Lấy toàn bộ dữ liệu game', description: 'Chép mọi file dữ liệu (RomFS) và file chương trình (ExeFS) ra khỏi file game (.nsp hoặc .xci), vào romfs/ và exefs/ trong thư mục bạn chọn, giống bước thiết lập dự án từ đầu. Game này khoảng 5,7 GB, phần lớn là giọng nói.', note: 'Không hỗ trợ file cập nhật; hãy dùng bản game gốc. Bấm Dừng thì những gì đã lấy ra được xoá đi.'},
  'rrlib-romfs': {title: 'Lấy vài file ra khỏi game', description: 'Chép những file dữ liệu bạn chọn (ví dụ common/script.memfs và common/script.membody) ra từ file game (.nsp), không phải bung cả 5 GB. Tích List để xem tên mọi file trước.', note: 'Không hỗ trợ file cập nhật; hãy dùng bản game gốc.'},
  'rrlib-exefs': {title: 'Lấy file chương trình của game', description: 'Chép các file chương trình (main, sdk, ...) ra từ file game (.nsp).'},
  'rrlib-memfs-list': {title: 'Xem danh sách kịch bản', description: 'Liệt kê mọi kịch bản trong script.memfs, vị trí của nó trong script.membody, bản nào game thật sự nạp, và những phần dữ liệu không ai trỏ tới. Không thay đổi gì.'},
  'rrlib-memfs-unpack': {title: 'Bung các kịch bản', description: 'Lưu từng kịch bản trong gói thành file .tat để mở bằng các tool kịch bản.'},
  'rrlib-memfs-check': {title: 'Kiểm tra gói kịch bản', description: 'Kiểm tra mọi kịch bản trong gói đều mở được và dựng lại giống từng byte. Dùng khi nghi file bị hỏng.'},
  'rrlib-rson-dump': {title: 'Xem mục lục kịch bản', description: 'In mục lục kịch bản (script.memfs) ra dạng chữ: tên từng file, vị trí và dung lượng.'},
  'rrlib-rson-check': {title: 'Kiểm tra mục lục kịch bản', description: 'Đọc mục lục kịch bản rồi ghi lại; bản ghi lại phải giống file gốc từng byte.'},
  'rrlib-kuv-strings': {title: 'Xem các câu của một kịch bản', description: 'Liệt kê mọi câu của một kịch bản (.tat), đánh số giống cột const_index trong bảng dịch.'},
  'rrlib-kuv-calls': {title: 'Xem lệnh của một kịch bản', description: 'Liệt kê các lệnh của một kịch bản (.tat) kèm câu chúng hiện ra, như NameMess, GuideMess, KW và WinClear.'},
  'rrlib-kuv-check': {title: 'Kiểm tra một kịch bản', description: 'Kiểm tra một kịch bản (.tat) mở được và dựng lại giống từng byte.'},
  'rrlib-exehook': {title: 'Tìm chuyển hướng trong file chương trình', description: 'Liệt kê những lần đọc kịch bản mà file chương trình đã vá (exefs/main) chuyển sang chỗ khác. Bản patch cũ dùng cách này cho ba kịch bản mở đầu.'},
  'rrlib-apply': {title: 'Ghi bảng dịch vào game', description: 'Ghi bảng dịch (.xlsx) vào script.memfs và script.membody: từng câu được ngắt dòng và mã hoá theo font tiếng Việt của bản mod, giữ nguyên tag như trong bảng dịch, rồi tự kiểm tra kết quả. Kiểm tag bằng Kiểm tra bản patch. Những câu bảng dịch không có dòng (tên nhân vật, lựa chọn) giữ chữ của bản mod.', note: 'Chạy thử trước rồi mới hỏi có ghi không. Dòng nào không ghi thì giữ câu của bản mod; báo cáo ghi rõ lý do.'},
  'rrlib-audit': {title: 'Kiểm tra bản patch', description: 'So bản patch tiếng Việt với kịch bản tiếng Nhật: tag vị trí, tag tên và tag dừng bị mất, câu bị đẩy ra ngoài màn hình, header sai. Không thay đổi gì.'},
  'rrlib-patch': {title: 'Dựng lại bản patch', description: 'Dựng lại script.memfs và script.membody: trả lại tag vị trí #P bị mất, giữ cho các câu mà bản Nhật đặt ngoài màn hình vẫn hiện ra, trỏ thẳng từng kịch bản tới dữ liệu của nó rồi tự kiểm tra kết quả.', note: 'Chạy thử trước rồi mới hỏi có ghi không. Hãy thử bản dựng trong game trước khi chia sẻ.'},
  'rrlib-sheetfix': {title: 'Danh sách sửa tag cho bảng dịch', description: 'Đọc bảng dịch (.xlsx) và ghi ra một file đề xuất theo đúng tab và dòng: tag #P cần thêm, câu phải để không có tag, và các câu #T / #KW cần sửa tay.'},
  'rrlib-sprite-export': {title: 'Lấy ảnh của một màn hình ra', description: 'Chữ ở menu, nút bấm và câu chú thích được vẽ sẵn trong ảnh. Công cụ lưu từng ô của một màn hình thành một file ảnh riêng trong một thư mục trống, đặt tên theo phần hình dùng nó (chữ 新しく始める ở menu tiêu đề là mat_ttlm_com01_off, câu chú thích của nó là mat_ttlm_com01_setu), kèm file cells_<tên màn hình>.csv ghi vị trí từng ô. Vẽ lại các ô cần dịch ngay trong thư mục đó, rồi dùng "Đưa ảnh đã vẽ lại vào game": app đã điền sẵn màn hình và thư mục cho bước đó.',
    args: {
      screen: {label: 'Màn hình', help: 'File .memfs của màn hình cần dịch, trong romfs/spec_win/ssdata. Ví dụ ttlm_nam.memfs là menu tiêu đề. File .membody cùng tên phải nằm cạnh nó.'},
      'output folder': {label: 'Thư mục ảnh', help: 'Nên chọn một thư mục trống: ảnh được lưu vào đây. Nếu thư mục đã có ảnh, app hỏi trước khi ghi đè và chép các ô bạn đã vẽ lại sang file .bak trước. Bỏ trống thì chỉ xem danh sách các ô.'}
    }},
  'rrlib-sprite-import': {title: 'Đưa ảnh đã vẽ lại vào game', description: 'Đọc thư mục mà "Lấy ảnh của một màn hình ra" đã lưu, sau khi bạn vẽ lại các ô trong đó: ô nào khác bản game thì được dán lại đúng chỗ. Ô vẽ to hơn (cho chữ Việt dài hơn) được đặt vào một chỗ trống trong cùng tấm ảnh, và game vẫn vẽ nó quanh tâm của chữ cũ. Sau đó file của màn hình được dựng lại vào thư mục Ghi vào và tự kiểm tra; file không sửa giữ nguyên từng byte. Chạy xong bước lấy ảnh ra, app tự điền màn hình và thư mục ảnh ở đây.',
    args: {
      screen: {label: 'Màn hình', help: 'File .memfs của màn hình cần dịch, trong romfs/spec_win/ssdata. Ví dụ ttlm_nam.memfs là menu tiêu đề. File .membody cùng tên phải nằm cạnh nó.'},
      'image folder': {label: 'Thư mục ảnh', help: 'Thư mục mà bước lấy ảnh ra đã lưu (app tự điền), với các ô đã vẽ lại được lưu đè lên đúng file cũ: giữ tên, vẫn là PNG. Chữ cần chỗ thì ô được phép to hơn cỡ cũ.'},
      '--out': {label: 'Ghi vào', help: 'Thư mục romfs/spec_win/ssdata trong mod: file của màn hình được ghi vào đây. File cũ cùng tên được chép sang file .bak nằm cạnh nó trước khi ghi.'}
    }},
  'rrlib-sprite-check': {title: 'Kiểm tra file của một màn hình', description: 'Dựng lại một màn hình mà không sửa gì, kết quả phải giống từng byte, và thử nén lại mọi ảnh mà công cụ ghi được.',
    args: {screen: {label: 'Màn hình', help: 'File .memfs của màn hình, trong romfs/spec_win/ssdata. File .membody cùng tên phải nằm cạnh nó.'}}},
  'rrlib-exetext-export': {title: 'Lấy chữ trong file chương trình ra', description: 'Câu hỏi trong hộp thoại (前回と同じ名前を使用します｡), thông báo lưu nhanh, chú thích nút bấm, mục từ điển và tên chương nằm sẵn trong file chương trình (exefs/main) chứ không ở kịch bản: bảng dịch không có dòng nào cho chúng, và font tiếng Việt vẽ chúng thành chữ sai. Công cụ lưu mọi câu tiếng Nhật của file chương trình thành một danh sách (.csv) có cột vi_text trống để dịch; cột note ghi những gì phải giữ (%d, {B}, xuống dòng). Dịch xong thì dùng "Ghi chữ vào file chương trình": app đã điền sẵn file chương trình và danh sách cho bước đó.',
    args: {
      main: {label: 'File chương trình', help: 'exefs/main của bản mod (hoặc của bản Nhật).'},
      list: {label: 'Danh sách', help: 'Nơi lưu danh sách (.csv; muốn .xlsx thì cần openpyxl). Bỏ trống thì chỉ xem danh sách.'},
      '--map': {label: 'Bảng mã font', help: 'File .json mã hoá font. Với file chương trình công cụ này đã ghi, cột vi_text được điền sẵn bản dịch đang có trong đó.'}
    }},
  'rrlib-exetext-import': {title: 'Ghi chữ vào file chương trình', description: 'Ghi cột vi_text của danh sách vào exefs/main, mã hoá theo font tiếng Việt của bản mod, rồi tự kiểm tra kết quả. Mỗi câu dịch được đặt vào một vùng mới ở cuối file chương trình và mọi chỗ trỏ tới câu tiếng Nhật được trỏ sang nó, nên câu dịch dài hơn tiếng Nhật cũng được. Muốn sửa bản dịch thì chạy lại trên chính file main nó đã ghi: lần nào công cụ cũng dựng lại từ bản gốc.', note: 'Chạy thử trước rồi mới hỏi có ghi không. Câu nào chương trình tạo ra theo cách khác thì vẫn là tiếng Nhật: hãy thử từng màn hình trong game.',
    args: {
      main: {label: 'File chương trình', help: 'exefs/main của bản mod, đã dịch hay chưa đều được (app điền sẵn từ bước 1).'},
      list: {label: 'Danh sách', help: 'Danh sách từ bước 1 đã điền cột vi_text (.csv, hoặc .xlsx nếu có openpyxl).'},
      '--map': {label: 'Bảng mã font', help: 'File .json mã hoá font, lưu bằng "Ghi bảng dịch vào game" (ô Map).'},
      '--out': {label: 'Ghi vào', help: 'Nơi ghi file main mới: thư mục exefs trong mod. File main cũ ở đó được chép sang main.bak trước.'},
      '--report': {label: 'Báo cáo', help: 'File CSV ghi từng dòng của danh sách và việc đã làm với nó.'}
    }},
  'rrlib-exetext-check': {title: 'Kiểm tra chữ trong file chương trình', description: 'Liệt kê các câu tiếng Nhật tìm thấy trong exefs/main và những chỗ trỏ tới chúng, rồi thử dời tất cả sang vùng mới mà không đổi chữ: mọi chỗ trỏ phải đọc ra đúng câu cũ, và hoàn tác phải ra lại file chương trình giống từng byte. Không ghi gì.',
    args: {main: {label: 'File chương trình', help: 'exefs/main.'}}},
  'rrlib-font-gen': {title: 'Tạo font tiếng Việt', description: 'Vẽ lại chữ ASCII và chữ tiếng Việt của mọi font trong thư mục font tiếng Nhật bằng file font bạn chọn (.ttf/.otf), chỉnh cỡ cho khớp với chữ của game, rồi dựng font viền (outline) từ chính các chữ đó. Kana và kanji giữ nguyên. Có Bảng mã thì mỗi chữ Việt được vẽ vào đúng ô kana mà kịch bản của bản mod đang dùng cho nó, nên kịch bản hiện có hiện ngay kiểu chữ mới; chữ nào bảng mã chưa có (Ể, Ổ) được thêm ô với mã riêng, và Lưu bảng mã ghi kết quả lại để dùng cho "Ghi bảng dịch vào game" (ô Use map) và các tool chữ trong file chương trình.',
    note: 'Chạy thử trước rồi mới hỏi có ghi không. Công cụ báo khi chữ mới rộng hơn chữ của game, vì câu dài có thể tràn khung: hãy thử kết quả trong game.',
    args: {
      '--template': {label: 'Thư mục font gốc', help: 'Thư mục romfs/spec_win/font của bản tiếng Nhật.'},
      '--out': {label: 'Ghi vào', help: 'Thư mục romfs/spec_win/font trong mod. File cũ cùng tên được chép sang file .bak nằm cạnh nó trước khi ghi.'},
      '--font': {label: 'File font', help: 'File font có đủ chữ tiếng Việt (.ttf, .otf; file.ttc#1 để chọn một kiểu trong bộ). Thêm nhiều file để chữ nào file trước thiếu thì lấy ở file sau.'},
      '--font-standard': {label: 'Font cho standard (一)', help: 'File font (.ttf, .otf, .ttc) chỉ dùng cho font standard, lựa chọn フォント 一 trong cài đặt (gothic tròn), và bản viền của nó. Được thử trước File font.'},
      '--font-extra': {label: 'Font cho extra (二)', help: 'File font (.ttf, .otf, .ttc) chỉ dùng cho font extra, lựa chọn フォント 二 (gothic đậm), và bản viền của nó. Được thử trước File font.'},
      '--font-extra2': {label: 'Font cho extra2 (三)', help: 'File font (.ttf, .otf, .ttc) chỉ dùng cho font extra2, lựa chọn フォント 三 (viết tay), và bản viền của nó. Được thử trước File font.'},
      '--font-extra3': {label: 'Font cho extra3 (四)', help: 'File font (.ttf, .otf, .ttc) chỉ dùng cho font extra3, lựa chọn フォント 四 (có chân), và bản viền của nó. Được thử trước File font.'},
      '--font-ui': {label: 'Font cho ui', help: 'File font (.ttf, .otf, .ttc) chỉ dùng cho font ui (không nằm trong 4 lựa chọn フォント) và bản viền của nó. Được thử trước File font.'},
      '--map': {label: 'Bảng mã', help: 'File .json mã hoá font, lưu bằng "Ghi bảng dịch vào game" (ô Map). Thiếu nó thì chữ Việt trong kịch bản hiện tại hiện thành kana (ộ → ば).'},
      '--map-out': {label: 'Lưu bảng mã', help: 'Lưu bảng mã của font mới (.json) để dùng ở ô Use map.'},
      '--px-standard': {label: 'Cỡ chữ standard (一)', help: 'Cỡ chữ (pixel) chỉ cho font standard và bản viền của nó, thay cho ô Cỡ chữ. Bỏ trống thì tự chỉnh; lần chạy thử in cỡ tự chỉnh và chữ rộng hơn font gốc bao nhiêu.'},
      '--px-extra': {label: 'Cỡ chữ extra (二)', help: 'Cỡ chữ (pixel) chỉ cho font extra và bản viền của nó, thay cho ô Cỡ chữ. Bỏ trống thì tự chỉnh.'},
      '--px-extra2': {label: 'Cỡ chữ extra2 (三)', help: 'Cỡ chữ (pixel) chỉ cho font extra2 và bản viền của nó, thay cho ô Cỡ chữ. Bỏ trống thì tự chỉnh.'},
      '--px-extra3': {label: 'Cỡ chữ extra3 (四)', help: 'Cỡ chữ (pixel) chỉ cho font extra3 và bản viền của nó, thay cho ô Cỡ chữ. Bỏ trống thì tự chỉnh.'},
      '--px-ui': {label: 'Cỡ chữ ui', help: 'Cỡ chữ (pixel) chỉ cho font ui và bản viền của nó, thay cho ô Cỡ chữ. Bỏ trống thì tự chỉnh.'},
      '--px': {label: 'Cỡ chữ', help: 'Cỡ chữ (pixel) cho mọi font; bỏ trống thì mỗi font tự chỉnh cho chữ H cao bằng chữ của font gốc tương ứng.'},
      '--chars': {label: 'Thêm ký tự', help: 'Ký tự khác cần vẽ, mỗi ký tự ở mã riêng của nó.'},
      '--no-latin': {label: 'Giữ chữ ASCII của game', help: 'Không vẽ lại chữ ASCII, chỉ vẽ chữ tiếng Việt.'},
      '--outline-radius': {label: 'Độ dày viền', help: 'Độ dày viền tính bằng pixel; bỏ trống thì đo trên font tiếng Nhật.'}
    }},
  'rrlib-font-preview': {title: 'Xem trước font', description: 'Vẽ chữ bạn nhập bằng font của game ra file ảnh, xếp chữ như game làm. Chọn một file font, hoặc chọn cả thư mục font để vẽ chữ bằng 4 font trong cài đặt (一 二 三 四), font này dưới font kia, mỗi font có viền. Dùng để xem font trước khi thử trong game.',
    args: {
      font: {label: 'Font', help: 'Một font trong romfs/spec_win/font, ví dụ standard.font.memfs, hoặc chọn thư mục đó để xem 4 font trong cài đặt (一 二 三 四), mỗi font có viền.'},
      text: {label: 'Chữ', help: 'Dòng chữ cần vẽ; \\n để xuống dòng.'},
      image: {label: 'Ảnh', help: 'File ảnh cần lưu (.png).'},
      '--outline': {label: 'Font viền', help: 'Font viền đi kèm, ví dụ standard_outline.font.memfs. Chọn thư mục thì không cần.'},
      '--map': {label: 'Bảng mã', help: 'File .json mã hoá font: mã hoá dòng chữ trước, như kịch bản. Cần cho font dựng có Bảng mã, ví dụ font_map_installed.json.'}
    }},
  'rrlib-font-export': {title: 'Lấy ảnh của font ra', description: 'Lưu mọi ảnh của một font thành file PNG, kèm glyphs.tsv liệt kê từng ký tự với vị trí và độ rộng của nó. Không sửa gì.',
    args: {font: {label: 'Font', help: 'Một font trong romfs/spec_win/font, ví dụ standard.font.memfs.'}}},
  'rrlib-font-check': {title: 'Kiểm tra font', description: 'Đọc mọi font trong một thư mục rồi ghi lại mà không sửa gì; bản ghi lại phải giống file gốc từng byte.',
    args: {folder: {label: 'Thư mục', help: 'Một thư mục romfs/spec_win/font.'}}}
};

const engines = {
  otomate: {
    flow: 'Tạo bảng dịch → dịch cột C → gộp và khớp lại → ghi thoại vào game → đóng gói lại.',
    groups: {
      Build: {name: 'Giao diện', summary: 'Tạo file SYSTEM.cpk đã dịch từ các file trong dự án.'},
      Fonts: {name: 'Font', summary: 'Tạo và kiểm tra font của game.'},
      Archives: {name: 'File game', summary: 'Mở và đóng gói lại các file nén, file dữ liệu của game.'},
      Sheets: {name: 'Bảng dịch', summary: 'Tạo, kiểm tra và chuẩn bị bảng dịch.'},
      Apply: {name: 'Ghi bản dịch', summary: 'Đưa bản dịch vào các file của game.'},
      Executable: {name: 'File chương trình', summary: 'Dịch chữ nằm trong file chương trình của game, như các câu trích ở màn hình chính.'},
      Diagnostics: {name: 'Kiểm tra', summary: 'Kiểm tra chữ có bao nhiêu chỗ trên màn hình.'}
    }
  },
  unity: {
    flow: 'Xuất chữ ra bảng dịch → dịch → đưa bảng dịch vào game → chỉnh khung chữ → đóng gói mod.',
    groups: {
      Dump: {name: 'Lấy dữ liệu', summary: 'Chép file của game ra từ file .nsp, dùng prod.keys của bạn.'},
      Inspect: {name: 'Xem', summary: 'Xem bên trong file Unity trước khi sửa.'},
      Text: {name: 'Chữ', summary: 'Dịch chữ của game qua bảng dịch, hoặc sửa nhanh một từ.'},
      Layout: {name: 'Khung chữ', summary: 'Cho chữ đã dịch vừa khung: kích thước, xuống dòng, tự thu nhỏ.'},
      Fonts: {name: 'Font', summary: 'Thêm chữ tiếng Việt vào font của game, hoặc thay font.'},
      Executable: {name: 'Code game', summary: 'Sửa chữ nằm trong code của game. Dành cho người dùng nâng cao.'},
      Release: {name: 'Phát hành', summary: 'Đóng gói mod cho người chơi.'}
    }
  },
  rrlib: {
    flow: 'Lấy kịch bản ra khỏi game → ghi bảng dịch vào game → kiểm tra bản patch → thử trong game.',
    groups: {
      Dump: {name: 'Lấy dữ liệu', summary: 'Lấy toàn bộ game, hoặc từng file, ra khỏi file .nsp hoặc .xci, dùng prod.keys của bạn.'},
      Inspect: {name: 'Xem', summary: 'Xem bên trong mục lục, gói kịch bản và từng kịch bản.'},
      Patch: {name: 'Bản patch', summary: 'Ghi bảng dịch vào game, kiểm tra bản patch tiếng Việt so với kịch bản tiếng Nhật và dựng lại nó.'},
      Sheets: {name: 'Bảng dịch', summary: 'Từ bảng dịch ra danh sách các tag cần sửa.'},
      Images: {name: 'Ảnh giao diện', summary: 'Chữ ở menu, nút bấm và câu chú thích được vẽ sẵn trong ảnh: lấy ra thành file ảnh, vẽ lại rồi đưa vào game.'},
      Executable: {name: 'File chương trình', summary: 'Chữ nằm sẵn trong file chương trình (exefs/main): câu hỏi trong hộp thoại, thông báo lưu nhanh, chú thích nút bấm, từ điển và tên chương.'},
      Fonts: {name: 'Font', summary: 'Vẽ lại chữ Latin và chữ tiếng Việt trong font của game bằng file font bạn chọn, rồi xem trước kết quả.'}
    }
  }
};

const docs = {
  'DICH.md': 'Quy trình dịch',
  'CLAUDE.md': 'Ghi chú định dạng',
  'tools/README.md': 'Danh sách tool',
  'Font/README.md': 'Cài đặt font',
  'README.md': 'Hướng dẫn engine',
  'docs/01-data-layout.md': 'Cấu trúc dữ liệu',
  'docs/02-text-rendering.md': 'Cách hiển thị chữ',
  'docs/04-repacking.md': 'Đóng gói lại'
};

module.exports = {tools, engines, docs};
