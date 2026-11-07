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

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
}
function noteId(name) {
  return `note-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`;
}
function linkedNotes(name, text) {
  const found = [];
  const walk = nodes => {
    for (const node of nodes || []) {
      if (node.type === 'link') {
        const target = resolveDocLink(name, node.href);
        if (target?.file) found.push(target.file);
      }
      if (node.children) walk(node.children);
    }
  };
  const walkBlocks = blocks => {
    for (const block of blocks) {
      if (block.inlines) walk(block.inlines);
      if (block.items) for (const item of block.items) {
        walk(item.inlines);
        if (item.blocks) walkBlocks(item.blocks);
        if (item.children) walkBlocks([item.children]);
      }
      if (block.header) for (const cell of block.header) walk(cell);
      if (block.rows) for (const row of block.rows) for (const cell of row) walk(cell);
    }
  };
  walkBlocks(parseMarkdown(text));
  return found;
}
function hrefFor(current, href, known) {
  const target = resolveDocLink(current, href);
  if (!target) return null;
  if (target.external) return {href: target.external, external: true};
  const file = target.file || current;
  if (target.file && !known.has(file)) return null;
  const hash = target.hash ? `${noteId(file)}-${target.hash.slice(1)}` : noteId(file);
  return {href: `#${hash}`, external: false};
}
function inlinesToHtml(nodes, current, known) {
  return nodes.map(node => {
    if (node.type === 'text') return escapeHtml(node.text);
    if (node.type === 'code') return `<code>${escapeHtml(node.text)}</code>`;
    if (node.type === 'strong' || node.type === 'em') {
      const tag = node.type === 'strong' ? 'strong' : 'em';
      return `<${tag}>${inlinesToHtml(node.children, current, known)}</${tag}>`;
    }
    if (node.type === 'link') {
      const dest = hrefFor(current, node.href, known);
      const inner = inlinesToHtml(node.children, current, known);
      if (!dest) return inner;
      const extra = dest.external ? ' target="_blank" rel="noopener noreferrer"' : '';
      return `<a href="${escapeHtml(dest.href)}"${extra}>${inner}</a>`;
    }
    return '';
  }).join('');
}
function blocksToHtml(blocks, file, known, used = new Set()) {
  return blocks.map(block => {
    if (block.type === 'heading') {
      const id = `${noteId(file)}-${slugify(plainText(block.inlines), used)}`;
      return `<h${block.level} id="${id}">${inlinesToHtml(block.inlines, file, known)}</h${block.level}>`;
    }
    if (block.type === 'paragraph') return `<p>${inlinesToHtml(block.inlines, file, known)}</p>`;
    if (block.type === 'quote') return `<blockquote><p>${inlinesToHtml(block.inlines, file, known)}</p></blockquote>`;
    if (block.type === 'code') return `<pre><code>${escapeHtml(block.text)}</code></pre>`;
    if (block.type === 'hr') return '<hr>';
    if (block.type === 'list') {
      const tag = block.ordered ? 'ol' : 'ul';
      const start = block.ordered && block.start > 1 ? ` start="${block.start}"` : '';
      const items = block.items.map(item => `<li>${inlinesToHtml(item.inlines, file, known)}${item.blocks ? blocksToHtml(item.blocks, file, known, used) : ''}${item.children ? blocksToHtml([item.children], file, known, used) : ''}</li>`).join('');
      return `<${tag}${start}>${items}</${tag}>`;
    }
    if (block.type === 'table') {
      const head = block.header.map(cell => `<th>${inlinesToHtml(cell, file, known)}</th>`).join('');
      const rows = block.rows.map(row => `<tr>${row.map(cell => `<td>${inlinesToHtml(cell, file, known)}</td>`).join('')}</tr>`).join('');
      return `<table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`;
    }
    return '';
  }).join('\n');
}
function documentationPage({title, intro, pages}) {
  const known = new Set(pages.map(page => page.name));
  const nav = pages.map(page => `<a href="#${noteId(page.name)}">${escapeHtml(page.label)}</a>`).join('');
  const articles = pages.map(page => `<article id="${noteId(page.name)}"><h1>${escapeHtml(page.label)}</h1>${blocksToHtml(parseMarkdown(page.text), page.name, known)}</article>`).join('\n');
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>
:root{color-scheme:light;--ink:#241f33;--muted:#5c5670;--line:#e6e3ee;--field:#f4f2f8;--accent:#4c32b3}
*{box-sizing:border-box}
body{margin:0;background:#f7f6fb;color:var(--ink);font:16px/1.6 ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif}
.layout{display:grid;grid-template-columns:240px minmax(0,1fr);min-height:100vh}
nav{position:sticky;top:0;align-self:start;max-height:100vh;overflow:auto;padding:28px 18px;border-right:1px solid var(--line);background:#fcfbfe}
nav p{margin:0 0 16px;color:var(--muted);font-size:13px;line-height:1.5}
nav a{display:block;margin:2px 0;padding:8px 10px;border-radius:8px;color:var(--ink);text-decoration:none;font-size:14px}
nav a:hover{background:#efeafc}
main{padding:36px 40px 64px;max-width:820px}
article{padding-bottom:28px;margin-bottom:28px;border-bottom:1px solid var(--line)}
article:last-child{border-bottom:0}
h1{font-size:32px;line-height:1.2;letter-spacing:-.03em;margin:0 0 16px}
h2{font-size:22px;margin:28px 0 10px}
h3,h4{font-size:18px;margin:22px 0 8px}
p,li{font-size:16px}
a{color:var(--accent)}
code{font-family:ui-monospace,'SF Mono',Consolas,monospace;font-size:13px;background:var(--field);padding:1px 5px;border-radius:4px}
pre{padding:14px 16px;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:auto}
pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;font-size:14px;margin:0 0 16px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:var(--field)}
blockquote{margin:0 0 14px;padding-left:12px;border-left:1px solid var(--line);color:var(--muted)}
@media(max-width:800px){.layout{grid-template-columns:1fr}nav{position:static;max-height:none;border-right:0;border-bottom:1px solid var(--line)}main{padding:24px 18px 48px}}
</style>
</head>
<body>
<div class="layout">
<nav><p>${escapeHtml(intro)}</p>${nav}</nav>
<main>${articles}</main>
</div>
</body>
</html>`;
}

if (typeof module !== 'undefined') module.exports = {parseMarkdown, resolveDocLink, renderMarkdown, linkedNotes, documentationPage};
