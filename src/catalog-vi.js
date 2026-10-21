// Vietnamese text for the tool catalogs, shown when the interface language is
// Vietnamese. Tool ids match catalog-otomate.js and catalog-unity.js; anything
// missing here falls back to the English in those files.
const DRY = 'Chỉ hiện những gì sẽ thay đổi cho tới khi bạn tích Apply. Nếu lưu đè lên file gốc, app giữ một bản sao lưu .bak.';

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
  'unity-release': {title: 'Đóng gói bản phát hành', description: 'Nén bản mod hoàn chỉnh thành file zip để người chơi cài vào Ryujinx hoặc Switch đã mod (Atmosphere).', note: 'Chỉ hiện kế hoạch cho tới khi bạn tích Build.'}
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
