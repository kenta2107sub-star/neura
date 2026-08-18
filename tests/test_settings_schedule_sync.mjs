import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const html = readFileSync(new URL('../docs/index.html', import.meta.url), 'utf8');

function extractFunction(name, { required = true } = {}) {
  const functionStart = html.indexOf(`function ${name}(`);
  if (functionStart === -1) {
    if (required) throw new Error(`docs/index.html に ${name}() がありません`);
    return '';
  }
  const asyncPrefix = 'async ';
  const start = html.slice(functionStart - asyncPrefix.length, functionStart) === asyncPrefix
    ? functionStart - asyncPrefix.length
    : functionStart;

  const braceStart = html.indexOf('{', start);
  let depth = 0;
  let quote = null;
  let escaped = false;
  for (let i = braceStart; i < html.length; i += 1) {
    const char = html[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === quote) quote = null;
      continue;
    }
    if (char === "'" || char === '"' || char === '`') {
      quote = char;
      continue;
    }
    if (char === '{') depth += 1;
    if (char === '}') {
      depth -= 1;
      if (depth === 0) return html.slice(start, i + 1);
    }
  }
  throw new Error(`${name}() の終端を検出できません`);
}

function makeCronHarness({ apiKey = 'cron-key', responses = [] } = {}) {
  const calls = [];
  const context = vm.createContext({
    getCronJobKey: () => apiKey,
    fetch: async (url, options) => {
      calls.push({ url, options });
      return responses.shift() ?? { ok: true };
    },
  });
  vm.runInContext(`${extractFunction('cronJobOrgUpdate')}; globalThis.run = cronJobOrgUpdate;`, context);
  return { run: context.run, calls };
}

function makeSaveHarness({ config, previous, cronResult = true, cronError = null } = {}) {
  const events = [];
  const elements = {
    'src-url-err': { style: {} },
    'cfg-sched-err': { style: {} },
    'settings-save-btn': { disabled: false, textContent: '[ 保存する ]' },
  };
  const scheduleSnapshotSource = extractFunction('scheduleSyncSnapshot', { required: false })
    || `function scheduleSyncSnapshot(schedules) {
      return schedules.map(({ hour, enabled, cron_job_id }) => ({ hour, enabled, cron_job_id }));
    }`;
  const context = vm.createContext({
    __initialPrevious: structuredClone(previous),
    cachedGeminiPrompt: '{articles}',
    collectFormConfig: () => structuredClone(config),
    document: {
      getElementById: id => elements[id],
      querySelectorAll: () => [],
    },
    getGithubCreds: () => ({ owner: 'owner', repo: 'repo', pat: 'pat' }),
    ghGetConfig: async () => ({ sha: 'sha' }),
    ghPutConfig: async () => events.push('github-save'),
    cronJobOrgUpdate: async () => {
      events.push('cron-sync');
      if (cronError) throw cronError;
      return cronResult;
    },
    showBanner: message => events.push(['banner', message]),
    hideBanner: () => events.push('hide-banner'),
    showToast: message => events.push(['toast', message]),
    ERROR_MESSAGES: { 'ERR-11': 'github error', 'ERR-14': 'cron error' },
  });
  vm.runInContext(`
    ${scheduleSnapshotSource}
    let prevSchedules = globalThis.__initialPrevious;
    ${extractFunction('saveSettings')}
    globalThis.run = saveSettings;
    globalThis.getPrevious = () => prevSchedules;
  `, context);
  return { run: context.run, getPrevious: context.getPrevious, events };
}

const enabledSlot = {
  hour: 19,
  enabled: true,
  cron_job_id: '1001',
  max_articles: 5,
  genres: { 'ニュース': true },
};
const disabledSlot = {
  hour: 8,
  enabled: false,
  cron_job_id: '7946648',
  max_articles: 10,
  genres: { 'ニュース': true },
};

test('cron-job.org同期は無効スロットも enabled:false でPATCHする', async () => {
  const harness = makeCronHarness();

  const didSync = await harness.run([enabledSlot, disabledSlot]);

  assert.equal(didSync, true);
  assert.equal(harness.calls.length, 2);
  assert.equal(harness.calls[1].url, 'https://api.cron-job.org/jobs/7946648');
  assert.deepEqual(JSON.parse(harness.calls[1].options.body), { job: { enabled: false } });
});

test('有効スロットはenabled:trueとJSTスケジュールをPATCHする', async () => {
  const harness = makeCronHarness();

  await harness.run([enabledSlot]);

  assert.deepEqual(JSON.parse(harness.calls[0].options.body), {
    job: {
      enabled: true,
      schedule: {
        timezone: 'Asia/Tokyo',
        hours: [19],
        minutes: [0],
        mdays: [-1],
        months: [-1],
        wdays: [-1],
      },
    },
  });
});

test('APIキー未設定は外部同期を行わず false を返す', async () => {
  const harness = makeCronHarness({ apiKey: '' });

  assert.equal(await harness.run([enabledSlot, disabledSlot]), false);
  assert.equal(harness.calls.length, 0);
});

test('スケジュール同期用スナップショットは時刻・有効状態・ジョブIDだけを保持する', () => {
  const source = extractFunction('scheduleSyncSnapshot');
  const context = vm.createContext({});
  vm.runInContext(`${source}; globalThis.run = scheduleSyncSnapshot;`, context);

  const snapshot = JSON.parse(JSON.stringify(context.run([enabledSlot])));
  assert.deepEqual(snapshot, [{ hour: 19, enabled: true, cron_job_id: '1001' }]);
});

test('ジャンルと件数だけの変更ではcron-job.org同期を行わない', async () => {
  const previous = [{ hour: 19, enabled: true, cron_job_id: '1001' }];
  const changedPresentation = { ...enabledSlot, max_articles: 9, genres: { 'ニュース': false } };
  const harness = makeSaveHarness({ config: { sources: [], notify_schedules: [changedPresentation] }, previous });

  await harness.run();

  assert.equal(harness.events.includes('cron-sync'), false);
  assert.deepEqual(JSON.parse(JSON.stringify(harness.getPrevious())), previous);
});

test('APIキー未設定時は同期済みスケジュールを更新しない', async () => {
  const previous = [{ hour: 13, enabled: true, cron_job_id: '1001' }];
  const harness = makeSaveHarness({
    config: { sources: [], notify_schedules: [enabledSlot, disabledSlot] },
    previous,
    cronResult: false,
  });

  await harness.run();

  assert.deepEqual(JSON.parse(JSON.stringify(harness.getPrevious())), previous);
});

test('cron-job.org同期失敗時はERR-14を消さず成功トーストも出さない', async () => {
  const previous = [{ hour: 13, enabled: true, cron_job_id: '1001' }];
  const harness = makeSaveHarness({
    config: { sources: [], notify_schedules: [enabledSlot, disabledSlot] },
    previous,
    cronError: { code: 'ERR-14' },
  });

  await harness.run();

  assert.deepEqual(JSON.parse(JSON.stringify(harness.getPrevious())), previous);
  assert.deepEqual(harness.events.filter(event => Array.isArray(event)), [['banner', 'cron error']]);
  assert.equal(harness.events.includes('hide-banner'), false);
});

test('全PATCH成功後だけ同期済みスケジュールを更新する', async () => {
  const previous = [{ hour: 13, enabled: true, cron_job_id: '1001' }];
  const harness = makeSaveHarness({
    config: { sources: [], notify_schedules: [enabledSlot, disabledSlot] },
    previous,
  });

  await harness.run();

  assert.deepEqual(JSON.parse(JSON.stringify(harness.getPrevious())), [
    { hour: 19, enabled: true, cron_job_id: '1001' },
    { hour: 8, enabled: false, cron_job_id: '7946648' },
  ]);
  assert.equal(harness.events.includes('hide-banner'), true);
  assert.equal(harness.events.some(event => Array.isArray(event) && event[0] === 'toast'), true);
});
