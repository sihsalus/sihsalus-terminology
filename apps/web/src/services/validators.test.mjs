/* eslint-env node, es2020 */
/* eslint-disable spellcheck/spell-checker -- Assertions cover the supported interface languages. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { transformFileSync } from '@babel/core';
import i18next from 'i18next';

const resources = Object.fromEntries(['en', 'es', 'zh'].map(language => [language, {
  translations: JSON.parse(readFileSync(new URL(`../i18n/locales/${language}/translations.json`, import.meta.url), 'utf8')),
}]));
const filename = fileURLToPath(new URL('../common/validators.js', import.meta.url));
const require = createRequire(filename);
const { code } = transformFileSync(filename, {
  babelrc: false, configFile: false,
  presets: [['@babel/preset-env', { targets: { node: '22' } }]],
});
const load = async (language = 'es') => {
  const i18n = i18next.createInstance();
  await i18n.init({ lng: language, resources, ns: ['translations'], defaultNS: 'translations', fallbackLng: false });
  const exports = {};
  vm.runInNewContext(code, {
    exports, require: name => name === 'i18next' ? i18n : require(name),
  }, { filename });
  return { ...exports, i18n };
};
const messages = {
  en: ['This field cannot be blank', 'Please select from suggestions', 'Invalid value'],
  es: ['Este campo no puede estar en blanco', 'Selecciona una de las sugerencias', 'Valor no válido'],
  zh: ['此字段不能为空', '请从建议中选择', '无效值'],
};

for(const language of ['en', 'es', 'zh']) {
  test(`shared validators use the real ${language} messages without fallback`, async () => {
    const { required, selected, matchPattern, MESSAGES } = await load(language);
    const validators = [required(), selected(), matchPattern(/^valid$/)];
    assert.deepEqual(validators.map(validator => validator.message), messages[language]);
    assert.deepEqual(Object.values(MESSAGES), messages[language]);
    for(const validator of validators) {
      assert.deepEqual(Object.keys(validator), ['isInvalid', 'message', 'type']);
      assert.equal(typeof validator.message, 'string');
      assert.equal(validator.type, 'error');
    }
  });
}

test('existing validators resolve the selected language when errors are collected', async () => {
  const { required, selected, matchPattern, applyValidatorsOn, VALUE_NOT_SELECTED, i18n } = await load('en');
  const fields = {
    required: { value: '', validators: [required()] },
    selected: { value: VALUE_NOT_SELECTED, validators: [selected()] },
    pattern: { value: 'invalid', validators: [matchPattern(/^valid$/)] },
  };
  for(const language of ['en', 'es', 'zh', 'es']) {
    await i18n.changeLanguage(language);
    applyValidatorsOn(fields);
    assert.deepEqual(Object.values(fields).map(field => field.errors[0]), messages[language]);
    assert.ok(Object.values(fields).every(field => field.errors.length === 1));
  }
});

test('explicit validator messages are preserved across language changes', async () => {
  const { required, selected, matchPattern, i18n } = await load();
  const validators = [required('Required override'), selected('Selected override'), matchPattern(/^valid$/, 'Pattern override')];
  for(const language of ['es', 'en', 'zh']) {
    await i18n.changeLanguage(language);
    assert.deepEqual(validators.map(validator => validator.message), ['Required override', 'Selected override', 'Pattern override']);
  }
});

test('required retains the existing empty-value and number rules', async () => {
  const { required } = await load();
  const validator = required();
  for(const value of [undefined, null, '', [], {}, false, true])
    assert.equal(validator.isInvalid(value), true);
  for(const value of [0, 1, NaN, Infinity, ' ', 'valid', [''], { name: '' }])
    assert.equal(validator.isInvalid(value), false);
});

test('selected retains the sentinel and empty-value results', async () => {
  const { selected, VALUE_NOT_SELECTED } = await load();
  const validator = selected();
  assert.equal(validator.isInvalid(VALUE_NOT_SELECTED), true);
  assert.equal(validator.isInvalid(''), 0);
  for(const value of [undefined, null, 0, false, 'valid', {}])
    assert.equal(validator.isInvalid(value), false);
});

test('pattern retains matching and optional-value results', async () => {
  const { matchPattern } = await load();
  const validator = matchPattern(/^[a-z]+$/);
  assert.equal(validator.isInvalid('valid'), false);
  assert.equal(validator.isInvalid('INVALID'), true);
  assert.equal(validator.isInvalid(''), 0);
  assert.equal(validator.isInvalid(undefined), undefined);
  assert.equal(validator.isInvalid(null), undefined);
});

test('field validation preserves values and clears only applicable errors', async () => {
  const { required, matchPattern, applyValidatorsOn } = await load();
  const fields = {
    missing: { value: '', validators: [required()], errors: ['Previous error'] },
    valid: { value: 'valid', validators: [required(), matchPattern(/^valid$/)], errors: ['Previous error'] },
    noValidators: { value: 'unchanged', errors: ['Server error'] },
    noValue: { validators: [required()], errors: ['Server error'] },
  };
  assert.equal(applyValidatorsOn(fields), undefined);
  assert.deepEqual(Array.from(fields.missing.errors), [messages.es[0]]);
  assert.equal(fields.missing.value, '');
  assert.deepEqual(Array.from(fields.valid.errors), []);
  assert.equal(fields.valid.value, 'valid');
  assert.deepEqual(fields.noValidators.errors, ['Server error']);
  assert.deepEqual(fields.noValue.errors, ['Server error']);
});
