/* eslint-env node, es2020 */
/* eslint-disable spellcheck/spell-checker -- Fixtures include Spanish UI text and library configuration names. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import vm from 'node:vm';
import {transformFileSync} from '@babel/core';
import React from 'react';
import renderer, {act} from 'react-test-renderer';
import i18next from 'i18next';
import * as translation from 'react-i18next';

const require = createRequire(import.meta.url);
const es = JSON.parse(readFileSync(new URL('../i18n/locales/es/translations.json', import.meta.url)));
const load = file => {
  const filename = fileURLToPath(new URL(`../components/${file}.jsx`, import.meta.url));
  const {code} = transformFileSync(filename, {
    babelrc: false, configFile: false,
    presets: [['@babel/preset-env', {targets: {node: '22'}}], '@babel/preset-react'],
  });
  const exports = {};
  const modules = {
    react: React,
    'react-i18next': translation,
    '../../common/colors': {BLACK: '#000'},
    '../common/SelectItemText': 'SelectItemText',
    '@mui/material': Object.fromEntries(['Box', 'List', 'ListItemButton', 'ListItemIcon', 'ListItemText', 'ListSubheader', 'Checkbox', 'Button', 'Divider', 'Badge', 'LinearProgress', 'FormControl', 'Select', 'MenuItem', 'InputLabel'].map(name => [name, name])),
  };
  vm.runInNewContext(code, {exports, require: name => name in modules ? modules[name] : require(name)}, {filename});
  return exports.default;
};
const render = async (t, Component, props) => {
  const i18n = i18next.createInstance();
  await i18n.init({lng: 'es', resources: {es: {translation: es}}});
  let tree;
  await act(async () => { tree = renderer.create(React.createElement(translation.I18nextProvider, {i18n}, React.createElement(Component, props))); });
  t.after(() => tree.unmount());
  return tree;
};

test('reference filters use Spanish labels while retaining API values and clear behavior', async t => {
  const onChange = t.mock.fn();
  const tree = await render(t, load('repos/ReferenceFilters'), {onChange});
  const cases = [
    ['versioning', 'unversioned', 'Sin versión'],
    ['versioning', 'repository', 'Repositorio'],
    ['versioning', 'resource', 'Recurso'],
    ['definition_type', 'none', es.common.none],
    ['definition_type', 'intensional', 'Versiones de los recursos'],
    ['definition_type', 'extensional', 'Extensional / Enumerada'],
    ['cascade', 'any', 'Cualquiera'],
    ['cascade', 'none', es.common.none],
    ['cascade', 'sourcetoconcepts', es.reference.source_to_concepts],
    ['cascade', 'sourcemappings', es.reference.source_mappings],
    ['inclusion_type', 'include', es.reference.include],
    ['inclusion_type', 'exclude', es.reference.exclude],
  ];
  assert.deepEqual(tree.root.findAllByType('ListItemText').map(item => item.props.primary), cases.map(item => item[2]));
  for (const [index, [key, value]] of cases.entries()) {
    await act(async () => tree.root.findAllByType('ListItemButton')[index].props.onClick());
    await act(async () => tree.root.findAllByType('Button')[0].props.onClick());
    assert.deepEqual(JSON.parse(JSON.stringify(onChange.mock.calls.at(-1).arguments[0])), {[key]: value});
    await act(async () => tree.root.findAllByType('Button')[1].props.onClick());
    assert.deepEqual(JSON.parse(JSON.stringify(onChange.mock.calls.at(-1).arguments[0])), {});
    assert.ok(tree.root.findAllByType('Checkbox').every(item => !item.props.checked));
  }
});

for (const query of ['glucosa < 10', '<img src=x onerror=alert(1)>']) {
  test(`loading results is Spanish and treats query as text: ${query}`, async t => {
    const tree = await render(t, load('common/AutocompleteLoading'), {text: query});
    const text = node => typeof node === 'string' ? node : (node?.children || []).map(text).join('');
    assert.equal(text(tree.toJSON()), `Cargando resultados para ${query}`);
    assert.equal(tree.root.findAllByType('img').length, 0);
    assert.equal(tree.root.findAllByType('LinearProgress').length, 1);
  });
}

test('validation schema labels use Spanish without changing schema identifiers', async t => {
  const onChange = t.mock.fn();
  const tree = await render(t, load('repos/CustomValidationSchemaField'), {value: 'OpenMRS', onChange});
  assert.equal(tree.root.findByType('Select').props.value, 'OpenMRS');
  const items = tree.root.findAllByType('SelectItemText');
  assert.deepEqual(items.map(item => item.props.value), ['None', 'OpenMRS']);
  assert.deepEqual(items.map(item => item.props.secondaryText), ['Esquema de validación predeterminado', 'Esquema de validación personalizado de OpenMRS']);
  await act(async () => tree.root.findByType('Select').props.onChange({target: {value: 'None'}}));
  assert.deepEqual(Array.from(onChange.mock.calls[0].arguments), ['customValidationSchema', 'None']);
});
