const PAGE_SIZE = 8;

function fold(value) {
  return String(value || '').toLowerCase().normalize('NFD').replace(/\p{M}/gu, '').replace(/đ/g, 'd');
}

function commandOf(tool) {
  return [tool.script, ...(tool.prefix || [])].filter(Boolean).join(' ');
}

function toolsForEngine(tools, engineId) {
  return tools.filter(tool => tool.engine === engineId);
}

function browse(tools, {group = null, query = '', page = 1, pageSize = PAGE_SIZE} = {}) {
  const needle = fold(query.trim());
  const searching = needle.length > 0;
  const matches = tools.filter(tool => {
    if (searching) {
      return fold([tool.title, tool.description, tool.id, commandOf(tool), tool.group].join(' ')).includes(needle);
    }
    return !!group && tool.group === group;
  });
  const pageCount = Math.max(1, Math.ceil(matches.length / pageSize));
  const current = Math.min(Math.max(page, 1), pageCount);
  const start = (current - 1) * pageSize;
  return {
    tools: matches.slice(start, start + pageSize),
    total: matches.length,
    page: current,
    pageCount,
    pageSize,
    group: searching ? group : (group || null),
    searching
  };
}

function clearSearch(group) {
  return group || null;
}

function selectTool(tool) {
  return {
    purpose: tool.description || '',
    caution: tool.note || '',
    command: commandOf(tool),
    originalName: tool.title || '',
    runRequest: null
  };
}

module.exports = {PAGE_SIZE, browse, clearSearch, selectTool, toolsForEngine, commandOf};
