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

const context = vm.createContext({});
vm.runInContext(`
  ${extractUntil('categoryBadge', '\n\n  function sourceLabel')}
  ${extractUntil('importanceDots', '\n\n  function escHtml')}
  ${extractUntil('escHtml', '\n\n  /* key_points')}
  globalThis.categoryBadge = categoryBadge;
  globalThis.importanceDots = importanceDots;
`, context);

test('重要度に文字列が入っても属性の外へ抜けず、0〜5の数値として表示する', () => {
  const output = context.importanceDots('5" onmouseover="alert(1)" x="');

  assert.doesNotMatch(output, /onmouseover/);
  assert.match(output, /aria-label="重要度 0\/5"/);
});

test('重要度の数値は1〜5の範囲で表示し、範囲外は丸める', () => {
  assert.match(context.importanceDots(4), /aria-label="重要度 4\/5"/);
  assert.match(context.importanceDots(9), /aria-label="重要度 5\/5"/);
  assert.equal((context.importanceDots(3).match(/imp-seg--filled/g) || []).length, 3);
});

test('未知のカテゴリ名はHTMLとして解釈されない', () => {
  const output = context.categoryBadge('<img src=x onerror=alert(1)>');

  assert.doesNotMatch(output, /<img/);
  assert.match(output, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(context.categoryBadge('研究'), /badge-research/);
});
