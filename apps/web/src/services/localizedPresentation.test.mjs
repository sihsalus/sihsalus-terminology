/* eslint-env node, es2020 */
/* eslint-disable spellcheck/spell-checker -- Assertions include Spanish UI text and library configuration names. */
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
import moment from 'moment';
import 'moment/locale/es.js';

const require = createRequire(import.meta.url);
const es = JSON.parse(readFileSync(new URL('../i18n/locales/es/translations.json', import.meta.url)));

const load = (file, utils = {}, moduleOverrides = {}) => {
  const filename = fileURLToPath(new URL(`../components/${file}.jsx`, import.meta.url));
  const {code} = transformFileSync(filename, {
    babelrc: false, configFile: false,
    presets: [['@babel/preset-env', {targets: {node: '22'}}], '@babel/preset-react'],
  });
  const exports = {};
  const window = {location: {href: 'https://terminology.example/#/concepts/'}};
  const modules = {
    react: React,
    'react-i18next': translation,
    'react-router-dom': {useHistory: () => ({}), useLocation: () => ({pathname: '/orgs/SIHSALUS/sources/'}), useParams: () => ({user: 'synthetic'})},
    '../../common/colors': {BLACK: '#000', PRIMARY_COLORS: {main: '#4836ff'}},
    '../../common/utils': {isLoggedIn: () => false, getCurrentUser: () => ({}), hasAuthGroup: () => false, ...utils},
    '../../common/constants': {MAX_SEARCH_RESULT_WINDOW: 10000},
    './Property': 'Property',
    './sortConfig': {getSortConfig: () => ({})},
    './columns': {resolveColumns: () => []},
    './browseConfig': {BROWSE_CONFIG: {}, FACET_FILTER_CONFIG: {}},
    '../app/LayoutContext': {OperationsContext: React.createContext({contextRepo: {}})},
    '../repos/utils': {createSimilarRepoHref: () => false},
    '../references/ReferenceSourceGroupedResults': {__esModule: true, default: 'ReferenceSourceGroupedResults', getReferenceSourceGroups: () => []},
    '@mui/material': Object.fromEntries(['Alert', 'TextField', 'Box', 'Divider', 'Autocomplete', 'Dialog', 'DialogContent', 'DialogActions', 'DialogTitle', 'Button', 'Chip', 'Tooltip', 'Skeleton'].map(name => [name, name])),
    '@mui/material/Autocomplete': {createFilterOptions: () => options => options},
    '@mui/material/ListItemText': ({primary, secondary}) => React.createElement('ListItemText', {}, primary, secondary),
    '@mui/icons-material': {Add: 'AddIcon'},
    ...moduleOverrides,
  };
  vm.runInNewContext(code, {exports, window, require: name => {
    if (name in modules) return modules[name];
    if (name === 'lodash' || name.startsWith('lodash/')) return require(name);
    if (name.startsWith('@mui/') || name.startsWith('./') || name.startsWith('../')) return name.split('/').at(-1);
    throw new Error(`Unexpected import ${name}`);
  }}, {filename});
  return {Component: exports.default, window};
};

const render = async (t, Component, props) => {
  const i18n = i18next.createInstance();
  await i18n.init({lng: 'es', resources: {es: {translation: es}}});
  let tree;
  await act(async () => {
    tree = renderer.create(React.createElement(translation.I18nextProvider, {i18n}, React.createElement(Component, props)));
  });
  t.after(() => tree.unmount());
  return tree;
};

for (const allowed of [false, true]) {
  test(`profile registration date uses Spanish and preserves edit permission=${allowed}`, async t => {
    const user = Object.freeze({name: 'Synthetic Name', username: 'synthetic', date_joined: '2026-10-21T12:00:00', url: '/users/synthetic/'});
    const formatDate = t.mock.fn(value => moment(value).locale('es').format('L'));
    const canEditUser = t.mock.fn(() => allowed);
    const get = t.mock.fn(async () => ({data: {}}));
    const {Component} = load('users/UserProfile', {
      formatDate, canEditUser, sortOrgs: value => value,
      formatWebsiteLink: () => '', getCurrentUser: () => ({username: 'synthetic'}),
    }, {'../../services/APIService': {users: () => ({appendToUrl: () => ({get})})}});
    const tree = await render(t, Component, {user});
    const dateLabel = tree.root.findAllByType('Typography').find(item => item.props.component === 'h1');
    assert.equal(React.Children.toArray(dateLabel.props.children).join(''), 'Fecha de registro 21/10/2026');
    assert.equal(formatDate.mock.calls[0].arguments[0], user.date_joined);
    assert.equal(canEditUser.mock.calls[0].arguments[0], user.username);
    assert.equal(tree.root.findAllByType('Link').length, allowed ? 1 : 0);
    if (allowed) assert.equal(tree.root.findByType('Link').props.href, '#/users/synthetic/edit');
    assert.equal(get.mock.callCount(), allowed ? 1 : 0);
    assert.equal(user.date_joined, '2026-10-21T12:00:00');
    assert.equal(tree.root.findByType('UserIcon').props.user, user);
  });
}

test('concept summary translates labels and preserves clinical values', async t => {
  const {Component} = load('concepts/ConceptSummaryProperties');
  const tree = await render(t, Component, {concept: {concept_class: 'Diagnosis', datatype: 'Coded'}});
  const properties = tree.root.findAllByType('Property');
  assert.deepEqual(properties.map(item => item.props.code), ['Clase', 'Tipo de dato']);
  assert.deepEqual(properties.map(item => item.props.value), ['Diagnosis', 'Coded']);
});

test('custom property labels supplied by a catalog remain unchanged', async t => {
  const {Component} = load('concepts/ConceptSummaryProperties');
  const tree = await render(t, Component, {concept: {property: [{code: 'custom_code', valueString: 'Original value', display: 'Clinical owner label'}]}});
  assert.equal(tree.root.findByType('Property').props.code, 'Clinical owner label');
  assert.equal(tree.root.findByType('Property').props.value, 'Original value');
});

for (const enabled of [true, false]) {
  test(`401 uses Spanish action text and preserves registration=${enabled}`, async t => {
    const getLoginURL = t.mock.fn(async () => 'https://identity.example/login');
    const getRegisterURL = t.mock.fn(async () => 'https://identity.example/register');
    const {Component, window} = load('errors/Error401', {isSelfRegistrationEnabled: () => enabled, getLoginURL, getRegisterURL});
    const tree = await render(t, Component, {});
    const links = tree.root.findAllByType('a');
    assert.equal(links.length, enabled ? 2 : 1);
    assert.equal(React.Children.toArray(links[0].props.children).join(''), 'Inicia sesión');
    await act(async () => links[0].props.onClick({preventDefault() {}}));
    assert.equal(getLoginURL.mock.calls[0].arguments[0], 'https://terminology.example/#/concepts/');
    assert.equal(window.location.href, 'https://identity.example/login');
    if (enabled) {
      assert.equal(React.Children.toArray(links[1].props.children).join(''), 'crea una cuenta');
      await act(async () => links[1].props.onClick({preventDefault() {}}));
      assert.equal(window.location.href, 'https://identity.example/register');
    } else assert.equal(getRegisterURL.mock.callCount(), 0);
  });
}

test('search pagination and selected results use Spanish without changing counts', async t => {
  const {Component} = load('search/SearchResults');
  const tree = await render(t, Component, {resource: 'concepts', selected: ['one'], results: {total: 123, page: 1, pageSize: 25, results: [{id: 'one'}]}});
  const pagination = tree.root.findByType('TablePagination');
  assert.equal(pagination.props.count, 123);
  assert.equal(pagination.props.labelDisplayedRows({from: 1, to: 25, count: 123}), '1–25 de 123');
  assert.equal(pagination.props.labelDisplayedRows({from: 1, to: 25, count: -1}), '1–25 de más de 25');
  assert.ok(JSON.stringify(tree.toJSON()).includes('1 seleccionado'));
});

test('custom language dialog translates controls without changing language codes', async t => {
  const {Component} = load('concepts/LocaleAutoComplete');
  const onChange = t.mock.fn();
  const tree = await render(t, Component, {cachedLocales: [{id: 'en', locale: 'en', name: 'English'}], value: 'en', custom: true, onChange});
  const autocomplete = tree.root.findByType('Autocomplete');
  assert.equal(autocomplete.props.value.id, 'en');
  assert.equal(autocomplete.props.value.name, 'English');
  assert.deepEqual(tree.root.findAllByType('Button').map(button => button.props.children), ['Cancelar', 'Guardar']);
  assert.equal(onChange.mock.callCount(), 0);
});

for (const query of ['glucosa < 10', '<img src=x onerror=alert(1)>']) {
test(`search suggestions preserve query text without interpreting markup: ${query}`, async t => {
  const {Component} = load('search/SearchInputDrawer');
  const initiateSearch = t.mock.fn();
  const tree = await render(t, Component, {open: true, input: query, initiateSearch});
  const text = node => typeof node === 'string' ? node : (node?.children || []).map(text).join('');
  const rendered = text(tree.toJSON());
  assert.ok(rendered.includes(`Buscar ${query} en los catálogos de SIHSALUS`), rendered);
  assert.ok(rendered.includes(`Buscar ${query} en todos los catálogos`), rendered);
  assert.equal(tree.root.findAllByType('img').length, 0);
  const globalOption = tree.root.findAllByType('ListItemButton').find(option => option.props.id === 'search_global');
  await act(async () => globalOption.props.onClick({persist() {}, currentTarget: {id: 'search_global'}}));
  assert.equal(initiateSearch.mock.calls[0].arguments[1], true);
  assert.equal(initiateSearch.mock.calls[0].arguments[2], false);
});
}
