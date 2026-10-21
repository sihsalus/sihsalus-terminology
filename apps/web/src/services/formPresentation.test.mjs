/* eslint-env node, es2020 */
/* eslint-disable spellcheck/spell-checker -- Fixtures include Spanish UI text and library configuration names. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import vm from 'node:vm';
import { transformFileSync } from '@babel/core';
import React from 'react';
import renderer, { act } from 'react-test-renderer';
import i18next from 'i18next';
import * as translation from 'react-i18next';

const require = createRequire(import.meta.url);
const es = JSON.parse(readFileSync(new URL('../i18n/locales/es/translations.json', import.meta.url)));
const validator = () => ({ isInvalid: () => false, message: '' });
const load = (file, overrides = {}) => {
  const filename = fileURLToPath(new URL(`../components/${file}.jsx`, import.meta.url));
  const { code } = transformFileSync(filename, {
    babelrc: false, configFile: false,
    presets: [['@babel/preset-env', { targets: { node: '22' } }], '@babel/preset-react'],
  });
  const modules = {
    react: React,
    'react-i18next': translation,
    'react-router-dom': { useHistory: () => ({}) },
    '@mui/material': { TextField: 'TextField', IconButton: 'IconButton', Tooltip: 'Tooltip', Button: 'MuiButton' },
    '@mui/material/Autocomplete': 'Autocomplete',
    '@mui/icons-material': { SwapVert: 'SwapIcon' },
    '../../common/validators': { required: validator, matchPattern: validator },
    '../../common/constants': { ID_REGEX: /^[a-zA-Z0-9-]+$/, NUM_REGEX: /[0-9.]+/, LANGUAGES: [{locale: 'es', name: 'Español'}] },
    '../app/LayoutContext': { OperationsContext: React.createContext({}) },
    '../../services/GAService': { recordUpsertEvent() {} },
    ...overrides,
  };
  const exports = {};
  const window = { location: { origin: 'https://terminology.example' } };
  const document = { getElementById: () => ({ reportValidity: () => true }) };
  vm.runInNewContext(code, { exports, window, document, require: name => {
    if(name in modules) return modules[name];
    if(name === 'lodash' || name.startsWith('lodash/')) return require(name);
    if(name.startsWith('@mui/') || name.startsWith('.')) return name.split('/').at(-1);
    throw new Error(`Unexpected import ${name}`);
  } }, { filename });
  return exports;
};

const render = async (t, Component, props) => {
  const i18n = i18next.createInstance();
  await i18n.init({ lng: 'es', resources: { es: { translation: es } } });
  let tree;
  await act(async () => {
    tree = renderer.create(React.createElement(translation.I18nextProvider, { i18n }, React.createElement(Component, { t: i18n.t.bind(i18n), ...props })));
  });
  t.after(() => tree.unmount());
  return tree;
};
const text = node => typeof node === 'string' ? node : Array.isArray(node) ? node.map(text).join('') : (node?.children || []).map(text).join('');

test('mapping automatic ID messages preserve manual toggles, clinical codes and submit values', async t => {
  const base = load('common/FormComponent');
  const post = t.mock.fn(() => ({ then() {} }));
  const service = { overrideURL: () => service, appendToUrl: () => service, post };
  const Component = load('mappings/MappingForm', {
    '../common/FormComponent': { __esModule: true, default: base.default, CardSection: 'CardSection' },
    './utils': { fetchMapTypes: callback => callback([{ id: 'SAME-AS', name: 'SAME-AS' }]) },
    '../../common/utils': { arrayToObject: entries => Object.fromEntries(entries.map(item => [item.key, item.value])) },
    '../../services/APIService': { new: () => service },
  }).default;
  const source = { id: 'Synthetic', url: '/orgs/SIHSALUS/sources/Synthetic/', autoid_mapping_mnemonic: 'sequential', autoid_mapping_external_id: 'uuid' };
  const tree = await render(t, Component, { source, repo: source });
  const initialText = text(tree.toJSON());
  assert.ok(initialText.includes('El ID del mapeo se asignará automáticamente.'));
  assert.ok(initialText.includes('El ID externo del mapeo se asignará automáticamente.'));
  const manualLinks = tree.root.findAllByType('a');
  assert.equal(manualLinks.length, 2);
  await act(async () => manualLinks[0].props.onClick());
  await act(async () => manualLinks[1].props.onClick());
  const instance = tree.root.findByType(Component).instance;
  assert.equal(instance.state.manualMnemonic, true);
  assert.equal(instance.state.manualExternalId, true);
  const id = tree.root.findAllByType('TextField').find(field => field.props.id === 'id');
  const external = tree.root.findAllByType('TextField').find(field => field.props.id === 'external_id');
  assert.equal(id.props.label, 'ID del mapeo');
  assert.equal(external.props.label, 'ID externo');
  await act(async () => id.props.onChange({ target: { id: 'id', value: 'M-1' } }));
  await act(async () => external.props.onChange({ target: { id: 'external_id', value: 'EX-1' } }));
  await act(async () => instance.onAutoCompleteChange('map_type', { id: 'SAME-AS' }));
  await act(async () => instance.onSourceSelect('to', source));
  await act(async () => instance.onConceptSelect('from', { url: `${source.url}concepts/C-1/`, display_name: 'Clinical source' }));
  await act(async () => instance.onConceptSelect('to', { url: `${source.url}concepts/C-2/`, display_name: 'Clinical target' }));
  const swap = tree.root.findByType('IconButton');
  assert.equal(swap.props['aria-label'], 'Intercambiar conceptos de origen y destino');
  await act(async () => swap.props.onClick());
  assert.equal(instance.state.fields.from_concept_url.value, `${source.url}concepts/C-2/`);
  await act(async () => instance.onSubmit({ preventDefault() {}, stopPropagation() {} }));
  const payload = post.mock.calls[0].arguments[0];
  assert.equal(payload.id, 'M-1');
  assert.equal(payload.external_id, 'EX-1');
  assert.equal(payload.map_type, 'SAME-AS');
  assert.equal(payload.from_concept_name, 'Clinical target');
  assert.equal(payload.to_concept_name, 'Clinical source');
});

test('user form translates the URL caption without changing identity controls or profile payload', async t => {
  const put = t.mock.fn(() => ({ then() {} }));
  const user = { username: 'synthetic', email: 'synthetic@pucp.edu.pe', first_name: 'Original', last_name: 'Name', preferred_locale: 'es', url: '/users/synthetic/' };
  const Component = load('users/UserForm', {
    '../../common/utils': { getCurrentUser: () => user },
    '../../services/APIService': { users: () => ({ put }) },
  }).default;
  const tree = await render(t, Component, { user });
  const content = text(tree.toJSON());
  assert.ok(content.includes('Tu URL será:'));
  assert.ok(content.includes('https://terminology.example/#/users/synthetic/'));
  const fields = tree.root.findAllByType('TextField');
  const email = fields.find(field => field.props.label === 'Correo electrónico');
  const username = fields.find(field => field.props.label === 'Nombre de usuario');
  assert.equal(email.props.disabled, true);
  assert.equal(email.props.value, user.email);
  assert.equal(username.props.disabled, true);
  assert.equal(username.props.value, user.username);
  await act(async () => tree.root.findByType('Button').props.onClick());
  const payload = put.mock.calls[0].arguments[0];
  assert.equal(payload.first_name, user.first_name);
  assert.equal(payload.last_name, user.last_name);
  assert.equal(payload.preferred_locale, 'es');
  assert.equal('email' in payload, false);
  assert.equal('username' in payload, false);
});
