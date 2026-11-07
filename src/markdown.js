// A small Markdown reader for the engine notes. It builds a block tree the page
// turns into elements, so a document never becomes raw HTML.

function isItem(line) {
  return /^\s*(?:[-*+]|\d+\.)\s+/.test(line);
}
function indentOf(line) {
  return line.match(/^\s*/)[0].length;
}
function isRule(line) {
  return /^([-*_])\1{2,}\s*$/.test(line);
}
function isHeading(line) {
  return /^#{1,6}\s+\S/.test(line);
}
function isFence(line) {
  return /^\s*```/.test(line);
}
// A fenced block, indented or not (a list item's commands sit under it). Its
// lines lose the indentation the opening fence had.
function parseFence(lines, index) {
  const indent = indentOf(lines[index]);
  const body = [];
  index++;
  while (index < lines.length && !isFence(lines[index])) {
    const line = lines[index++];
    body.push(line.slice(Math.min(indent, indentOf(line))));
  }
  if (index < lines.length) index++;
  return {block: {type: 'code', text: body.join('\n')}, index};
}
function isTableStart(lines, index) {
  const next = lines[index + 1] || '';
  return /^\s*\|/.test(lines[index]) && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(next);
}
function splitRow(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim());
}
function parseInline(text) {
  const nodes = [];
  const pattern = /(`[^`\n]+`)|(\*\*([^*]+)\*\*)|(\*([^*\n]+)\*)|(\[([^\]]+)\]\(([^)\s]+)\))/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) nodes.push({type: 'text', text: text.slice(last, match.index)});
    if (match[1]) nodes.push({type: 'code', text: match[1].slice(1, -1)});
    else if (match[2]) nodes.push({type: 'strong', children: parseInline(match[3])});
    else if (match[4]) nodes.push({type: 'em', children: parseInline(match[5])});
    else nodes.push({type: 'link', href: match[8], children: parseInline(match[7])});
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push({type: 'text', text: text.slice(last)});
  return nodes;
}
function parseList(lines, index) {
  const base = indentOf(lines[index]);
  const ordered = /^\s*\d+\.\s+/.test(lines[index]);
  // A numbered list a paragraph interrupted goes on from its own first number.
  const start = ordered ? Number(lines[index].match(/^\s*(\d+)\./)[1]) : 1;
  const items = [];
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      const following = lines[index + 1];
      if (following && isItem(following) && indentOf(following) >= base) { index++; continue; }
      if (following && isFence(following) && indentOf(following) > base && items.length) { index++; continue; }
      break;
    }
    if (isFence(line) && indentOf(line) > base && items.length) {
      const fence = parseFence(lines, index);
      (items[items.length - 1].blocks ||= []).push(fence.block);
      index = fence.index;
      continue;
    }
    if (isItem(line) && indentOf(line) === base && /^\s*\d+\.\s+/.test(line) !== ordered) break;
    if (isItem(line) && indentOf(line) > base) {
      const nested = parseList(lines, index);
      if (items.length) items[items.length - 1].children = nested.block;
      index = nested.index;
      continue;
    }
    if (isItem(line) && indentOf(line) === base) {
      items.push({inlines: parseInline(line.replace(/^\s*(?:[-*+]|\d+\.)\s+/, '')), children: null});
      index++;
      continue;
    }
    if (indentOf(line) > base && items.length) {
      const extra = parseInline(line.trim());
      const last = items[items.length - 1].inlines;
      last.push({type: 'text', text: ' '}, ...extra);
      index++;
      continue;
    }
    break;
  }
  return {block: {type: 'list', ordered, start, items}, index};
}
function parseMarkdown(source) {
  const lines = String(source).replace(/\r\n/g, '\n').split('\n');
  const blocks = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) { index++; continue; }
    if (isFence(line)) {
      const fence = parseFence(lines, index);
      blocks.push(fence.block);
      index = fence.index;
      continue;
    }
    if (isHeading(line)) {
      const level = line.match(/^#+/)[0].length;
      blocks.push({type: 'heading', level, inlines: parseInline(line.slice(level).trim())});
      index++;
      continue;
    }
    if (isRule(line)) { blocks.push({type: 'hr'}); index++; continue; }
    if (isTableStart(lines, index)) {
      const header = splitRow(lines[index]);
      index += 2;
      const rows = [];
      while (index < lines.length && /^\s*\|/.test(lines[index])) rows.push(splitRow(lines[index++]).map(parseInline));
      blocks.push({type: 'table', header: header.map(parseInline), rows});
      continue;
    }
    if (isItem(line)) {
      const parsed = parseList(lines, index);
      blocks.push(parsed.block);
      index = parsed.index;
      continue;
    }
    if (/^>\s?/.test(line)) {
      const body = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) body.push(lines[index++].replace(/^>\s?/, ''));
      blocks.push({type: 'quote', inlines: parseInline(body.join(' '))});
      continue;
    }
    const paragraph = [line.trim()];
    index++;
    while (index < lines.length && lines[index].trim() && !isHeading(lines[index]) && !isFence(lines[index]) && !isRule(lines[index]) && !isItem(lines[index]) && !/^>\s?/.test(lines[index]) && !isTableStart(lines, index)) {
      paragraph.push(lines[index].trim());
      index++;
    }
    blocks.push({type: 'paragraph', inlines: parseInline(paragraph.join(' '))});
  }
  return blocks;
}

// A link in a note points at another note, a heading in one, or a web page.
function resolveDocLink(current, href) {
  if (!href || href.startsWith('#')) return href ? {hash: href} : null;
  let url;
  try { url = new URL(href, `https://docs.local/${current}`); }
  catch { return null; }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
  if (url.host !== 'docs.local') return {external: href};
  const file = decodeURIComponent(url.pathname.replace(/^\//, ''));
  if (!file.endsWith('.md') || file.split('/').some(part => !part || part === '.' || part === '..')) return null;
  return {file, hash: url.hash || ''};
}

function plainText(nodes) {
  return nodes.map(node => node.type === 'text' || node.type === 'code' ? node.text : plainText(node.children || [])).join('');
}
function slugify(text, used) {
  const base = plainText([{type: 'text', text}]).toLowerCase().normalize('NFD').replace(/\p{M}/gu, '').replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '') || 'section';
  let slug = base;
  let n = 2;
  while (used.has(slug)) slug = `${base}-${n++}`;
  used.add(slug);
  return slug;
}
function renderInlines(parent, nodes, onLink) {
  for (const node of nodes) {
    if (node.type === 'text') parent.append(node.text);
    else if (node.type === 'code') {
      const code = document.createElement('code');
      code.textContent = node.text;
      parent.append(code);
    } else if (node.type === 'strong' || node.type === 'em') {
      const el = document.createElement(node.type === 'strong' ? 'strong' : 'em');
      renderInlines(el, node.children, onLink);
      parent.append(el);
    } else if (node.type === 'link') {
      const link = document.createElement('a');
      link.href = '#';
      renderInlines(link, node.children, onLink);
      link.addEventListener('click', event => { event.preventDefault(); onLink(node.href); });
      parent.append(link);
    }
  }
}
function renderBlocks(parent, blocks, onLink, used = new Set()) {
  for (const block of blocks) {
    if (block.type === 'heading') {
      const heading = document.createElement(`h${block.level}`);
      heading.id = slugify(plainText(block.inlines), used);
      renderInlines(heading, block.inlines, onLink);
      parent.append(heading);
    } else if (block.type === 'paragraph' || block.type === 'quote') {
      const el = document.createElement(block.type === 'quote' ? 'blockquote' : 'p');
      renderInlines(el, block.inlines, onLink);
      parent.append(el);
    } else if (block.type === 'code') {
      const pre = document.createElement('pre');
      const code = document.createElement('code');
      code.textContent = block.text;
      pre.append(code);
      parent.append(pre);
    } else if (block.type === 'hr') parent.append(document.createElement('hr'));
    else if (block.type === 'list') {
      const list = document.createElement(block.ordered ? 'ol' : 'ul');
      if (block.ordered && block.start !== 1) list.start = block.start;
      for (const item of block.items) {
        const li = document.createElement('li');
        renderInlines(li, item.inlines, onLink);
        if (item.children) renderBlocks(li, [item.children], onLink, used);
        if (item.blocks) renderBlocks(li, item.blocks, onLink, used);
        list.append(li);
      }
      parent.append(list);
    } else if (block.type === 'table') {
      const table = document.createElement('table');
      const head = document.createElement('thead');
      const headRow = document.createElement('tr');
      for (const cell of block.header) {
        const th = document.createElement('th');
        renderInlines(th, cell, onLink);
        headRow.append(th);
      }
      head.append(headRow);
      const body = document.createElement('tbody');
      for (const row of block.rows) {
        const tr = document.createElement('tr');
        for (const cell of row) {
          const td = document.createElement('td');
          renderInlines(td, cell, onLink);
          tr.append(td);
        }
        body.append(tr);
      }
      table.append(head, body);
      parent.append(table);
    }
  }
}
function renderMarkdown(parent, source, onLink) {
  parent.classList.add('doc');
  renderBlocks(parent, parseMarkdown(source), onLink);
}

if (typeof module !== 'undefined') module.exports = {parseMarkdown, resolveDocLink, renderMarkdown};
