const strings = {
  'nav.patch': {en: 'Create patch', vi: 'Tạo bản vá'},
  'nav.tools': {en: 'All tools', vi: 'Các công cụ'},
  'stage.choose': {en: 'Choose your sheet', vi: 'Chọn bảng dịch'},
  'stage.create': {en: 'Create a patch', vi: 'Tạo bản vá'},
  'stage.try': {en: 'Try it in your game', vi: 'Thử trong game'},
  'task.prepare': {en: 'Prepare your translation', vi: 'Chuẩn bị bản dịch'},
  'task.check': {en: 'Check for problems', vi: 'Kiểm tra lỗi'},
  'task.create': {en: 'Create the patch files', vi: 'Tạo các file bản vá'},
  'patch.choose': {en: 'Choose your Excel file', vi: 'Chọn file Excel của bạn'},
  'patch.hint': {en: 'The latest version of your translation sheet', vi: 'Bảng dịch bạn vừa chỉnh sửa xong'},
  'patch.reject': {en: 'Choose a file ending in .xlsx. Download an online sheet as Excel first.', vi: 'Hãy chọn file có đuôi .xlsx. Nếu dùng sheet trực tuyến, tải xuống dưới dạng Excel trước.'},
  'patch.button': {en: 'Create new patch', vi: 'Tạo bản vá mới'},
  'patch.stop': {en: 'Stop', vi: 'Dừng'},
  'patch.open': {en: 'Open patch folder', vi: 'Mở thư mục bản vá'},
  'patch.another': {en: 'Choose a new file', vi: 'Chọn file mới'},
  'patch.output': {en: 'Save patches to', vi: 'Lưu bản vá vào'},
  'patch.setup': {en: 'Project setup is required before a patch can be created.', vi: 'Cần thiết lập dự án trước khi tạo bản vá.'},
  'patch.replace': {en: 'A patch is already in that folder. Replace it?', vi: 'Thư mục đã có bản vá. Ghi đè?'},
  'patch.stopped': {en: 'Stopped. No completed patch.', vi: 'Đã dừng. Chưa có bản vá hoàn chỉnh.'},
  'patch.blocked': {en: 'No patch has been created. Fix these rows and choose the corrected Excel file.', vi: 'Chưa tạo bản vá. Sửa các dòng này rồi chọn file Excel đã sửa.'},
  'tools.search': {en: 'Search all tools', vi: 'Tìm trong toàn bộ công cụ'},
  'tools.clear': {en: 'Clear search', vi: 'Xóa tìm kiếm'},
  'tools.chooseGroup': {en: 'Choose a tool group', vi: 'Chọn nhóm công cụ'},
  'tools.use': {en: 'Use this tool', vi: 'Dùng công cụ này'},
  'tools.close': {en: 'Close', vi: 'Đóng'},
  'tools.command': {en: 'Original tool name and command', vi: 'Tên công cụ gốc và lệnh tương ứng'},
  'engine.blocked': {en: 'Stop or finish the run before changing engine or opening other tools.', vi: 'Dừng hoặc chờ chạy xong trước khi đổi engine hay mở công cụ khác.'},
  'language.en': {en: 'English', vi: 'English'},
  'language.vi': {en: 'Vietnamese', vi: 'Tiếng Việt'}
};

function t(key, language) {
  const entry = strings[key];
  if (!entry) throw new Error(`Missing interface string: ${key}`);
  return language === 'vi' ? entry.vi : entry.en;
}

function entries() { return strings; }

// Loaded by main and the tests through require, and by the page as a plain script.
if (typeof module !== 'undefined') module.exports = {t, entries};
