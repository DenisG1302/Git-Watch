const {test} = require('node:test');
const assert = require('node:assert/strict');
const {create, detectLanguage, messages, storageKey} = require('../gitwatch/static/i18n.js');
const BranchLoader = require('../gitwatch/static/branch-loader.js');

test('saved language takes precedence over regional browser preferences', () => {
  assert.equal(detectLanguage('en', ['ru-RU']), 'en');
  assert.equal(detectLanguage('ru', ['en-US']), 'ru');
  assert.equal(detectLanguage(null, ['de-DE', 'ru-RU', 'en-US']), 'ru');
  assert.equal(detectLanguage('unsupported', ['en-GB']), 'en');
  assert.equal(detectLanguage(null, ['de-DE']), 'en');
});

test('changing the language updates messages, date locale and the next session', () => {
  const values = new Map();
  const storage = {getItem: key => values.get(key), setItem: (key, value) => values.set(key, value)};
  const current = create({storage, languages: ['ru-RU']});
  assert.equal(current.t('settings'), 'Настройки');
  assert.equal(current.locale, 'ru-RU');
  assert.equal(current.setLanguage('en'), true);
  assert.equal(current.t('settings'), 'Settings');
  assert.equal(current.locale, 'en-US');
  assert.equal(values.get(storageKey), 'en');
  assert.equal(create({storage, languages: ['ru-RU']}).language, 'en');
  assert.equal(current.setLanguage('unknown'), false);
  assert.equal(current.language, 'en');
});

test('blocked browser storage still permits language switching for the session', () => {
  const storage = {getItem() {throw new Error('blocked');}, setItem() {throw new Error('blocked');}};
  const current = create({storage, languages: ['ru-RU']});
  assert.equal(current.language, 'ru');
  assert.equal(current.setLanguage('en'), true);
  assert.equal(current.t('save'), 'Save');
});

test('repository names and interpolation characters remain literal data', () => {
  const current = create();
  const name = 'owner/{count}-$&-<example>';
  assert.equal(current.t('removeRepo', {name}), `Remove ${name}`);
  current.setLanguage('ru');
  assert.equal(current.t('removeRepo', {name}), `Удалить ${name}`);
});

test('both language catalogs preserve the same interpolation fields', () => {
  const fields = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();
  for (const [key, translations] of Object.entries(messages)) {
    assert.equal(translations.length, 2, key);
    assert.ok(translations.every(text => typeof text === 'string' && text.length), key);
    assert.deepEqual(fields(translations[0]), fields(translations[1]), key);
  }
});

test('branch error messages follow the currently selected language', async () => {
  const current = create({languages: ['ru-RU']});
  const loader = new BranchLoader(async () => ({branches: 'invalid'}), () => {}, {
    invalid: () => current.t('branchReadError'),
  });
  await loader.load('owner/project');
  assert.equal(loader.state.error, 'Не удалось прочитать список веток. Обнови список.');
  current.setLanguage('en');
  await loader.load('owner/project');
  assert.equal(loader.state.error, 'Could not read the branch list. Refresh the list.');
});
