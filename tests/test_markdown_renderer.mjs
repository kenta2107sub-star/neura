import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const html = readFileSync(new URL('../docs/index.html', import.meta.url), 'utf8');

function extractUntil(name, marker) {
  const start = html.indexOf(`function ${name}(`);
  if (start === -1) throw new Error(`docs/index.html に ${name}() がありません`);
  const end = html.indexOf(marker, start);
  if (end === -1) throw new Error(`${name}() の終端マーカーを検出できません`);
  return html.slice(start, end);
}

function render(markdown) {
  const context = vm.createContext({});
  vm.runInContext(`
    function escHtml(str) {
      return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    ${extractUntil('renderMarkdown', '\n\n  function highlightCode')}
    ${extractUntil('highlightCode', '\n\n  /* ── Read tracking')}
    globalThis.run = renderMarkdown;
  `, context);
  return context.run(markdown);
}

test('翻訳Markdown内のHTMLを文字列として表示し、実行可能な属性を残さない', () => {
  const output = render('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>');

  assert.match(output, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(output, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(output, /<script>|<img /);
});

test('許可したMarkdown記法はHTMLをエスケープしたまま表示する', () => {
  const output = render('## 見出し\n\n**強調** と `x < y`\n\n```python\nprint("<safe>")\n```');

  assert.match(output, /<h2>見出し<\/h2>/);
  assert.match(output, /<strong>強調<\/strong>/);
  assert.match(output, /<code>x &lt; y<\/code>/);
  assert.match(output, /&quot;&lt;safe&gt;&quot;/);
});
