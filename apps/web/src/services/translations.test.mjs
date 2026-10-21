/* eslint-env node, es2020 */
/* eslint-disable spellcheck/spell-checker -- Assertions include multilingual text and library configuration names. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { transformFileSync } from '@babel/core';
import i18next from 'i18next';
import moment from 'moment';

const readLocale = language => JSON.parse(readFileSync(new URL(`../i18n/locales/${language}/translations.json`, import.meta.url), 'utf8'));
const flatten = (object, prefix = '', values = {}) => {
  for(const [key, value] of Object.entries(object)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if(typeof value === 'object') flatten(value, path, values);
    else values[path] = value;
  }
  return values;
};
const english = flatten(readLocale('en'));
const spanish = flatten(readLocale('es'));
const markup = value => (value.match(/{{[^}]+}}|<\/?(?:\d+|[A-Za-z][\w-]*)\s*\/?>/g) || []).sort();

test('Spanish covers every English translation without empty values or fallback', () => {
  for(const key of Object.keys(english)) {
    assert.equal(typeof spanish[key], 'string', `Missing Spanish translation: ${key}`);
    assert.ok(spanish[key].trim(), `Empty Spanish translation: ${key}`);
  }
});

test('Spanish preserves every interpolation and translated component tag', () => {
  for(const [key, value] of Object.entries(english))
    assert.deepEqual(markup(spanish[key]), markup(value), `Translation markup changed: ${key}`);
});

test('navigation and activity additions exist in all supported languages', () => {
  const keys = [
    'common.open_navigation', 'common.account_menu', 'common.waitlist', 'common.try_again',
    'auth.redirecting', 'auth.redirect_failed',
    'dashboard.activity_filters', 'dashboard.usage_title', 'dashboard.api_requests',
    'dashboard.top_operation', 'dashboard.view_usage', 'dashboard.no_usage',
    'dashboard.welcome_title', 'dashboard.welcome_description', 'dashboard.welcome_registration',
    'user.your_recent_activity', 'user.recent_activity_for',
    ...Object.keys(english).filter(key => key.startsWith('dashboard.event_')),
  ];
  for(const language of ['en', 'es', 'zh']) {
    const translations = flatten(readLocale(language));
    for(const key of keys) {
      assert.ok(translations[key], `Missing ${language} translation: ${key}`);
      assert.deepEqual(markup(translations[key]), markup(english[key]), `Invalid ${language} markup: ${key}`);
    }
  }
});

test('real translation configuration keeps relative dates in the selected language', async () => {
  const filename = fileURLToPath(new URL('../i18n/config.js', import.meta.url));
  const require = createRequire(filename);
  const instance = i18next.createInstance();
  const document = { documentElement: { lang: '' } };
  const { code } = transformFileSync(filename, {
    babelrc: false, configFile: false,
    presets: [['@babel/preset-env', { targets: { node: '22' } }]],
  });
  vm.runInNewContext(code, { exports: {}, document, require: name => name === 'i18next' ? instance : require(name) }, { filename });
  assert.equal(instance.language, 'es');
  assert.equal(document.documentElement.lang, 'es');
  assert.equal(moment.locale(), 'es');
  assert.equal(moment.duration(-2, 'hours').humanize(true), 'hace 2 horas');
  assert.equal(instance.t('search.selected_count', { count: 1 }), '1 seleccionado');
  assert.equal(instance.t('search.selected_count', { count: 2 }), '2 seleccionados');
  await instance.changeLanguage('en');
  assert.equal(document.documentElement.lang, 'en');
  assert.equal(moment.duration(-2, 'hours').humanize(true), '2 hours ago');
  await instance.changeLanguage('zh');
  assert.equal(document.documentElement.lang, 'zh');
  assert.equal(moment.locale(), 'zh-cn');
  assert.equal(moment.duration(-2, 'hours').humanize(true), '2 小时前');
  await instance.changeLanguage('es-PE');
  assert.equal(document.documentElement.lang, 'es-PE');
  assert.equal(moment.locale(), 'es');
  assert.equal(moment.duration(-2, 'hours').humanize(true), 'hace 2 horas');
});

test('webpack keeps explicit Moment locales and excludes automatic locale loading', () => {
  const require = createRequire(import.meta.url);
  const config = require('../../webpack.config.js')({ NODE_ENV: 'development' });
  const plugin = config.plugins.find(item => item.constructor.name === 'IgnorePlugin');
  assert.ok(plugin);
  assert.equal(plugin.options.resourceRegExp.test('moment/locale/es'), false);
  assert.equal(plugin.options.resourceRegExp.test('moment/locale/zh-cn'), false);
  assert.equal(plugin.options.resourceRegExp.test('./locale'), true);
  assert.equal(plugin.options.contextRegExp.test('/node_modules/moment'), true);
});
