/* eslint-env node, es2020 */
/* eslint-disable spellcheck/spell-checker -- Fixtures include translated labels and library names. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { parseSync, transformFileSync, transformSync } from '@babel/core';
import React from 'react';
import renderer, { act } from 'react-test-renderer';
import i18next from 'i18next';
import * as translation from 'react-i18next';
import moment from 'moment';
import 'moment/locale/es.js';
import 'moment/locale/zh-cn.js';

const require = createRequire(import.meta.url);
const options = { babelrc: false, configFile: false, presets: [['@babel/preset-env', { targets: { node: '22' } }], '@babel/preset-react'] };
const es = JSON.parse(readFileSync(new URL('../i18n/locales/es/translations.json', import.meta.url)));
const load = (path, modules = {}) => {
  const filename = fileURLToPath(new URL(path, import.meta.url));
  const { code } = transformFileSync(filename, options);
  const exports = {};
  vm.runInNewContext(code, { exports, require: name => {
    if(name in modules) return modules[name];
    if(name.startsWith('.')) return {};
    return require(name);
  } }, { filename });
  return exports;
};

test('display date helpers follow locale and preserve date inputs and ISO serialization', () => {
  const { formatDate, formatDateTime } = load('../common/utils.js', { './constants': load('../common/constants.js') });
  const input = moment('2026-10-21T16:05:00').locale('en');
  const originalISO = input.toISOString();
  moment.locale('es');
  assert.equal(formatDate(input), '21/10/2026');
  assert.equal(formatDateTime(input), '21/10/2026 16:05');
  assert.equal(input.locale(), 'en');
  assert.equal(input.toISOString(), originalISO);
  assert.equal(input.format('YYYY-MM-DD'), '2026-10-21');
  moment.locale('en');
  assert.equal(formatDate(input), '10/21/2026');
  assert.equal(formatDateTime(input), '10/21/2026 4:05 PM');
  moment.locale('zh-cn');
  assert.equal(formatDate(input), '2026/10/21');
  moment.locale('es');
});

test('date picker localizes its presentation and keeps ISO query values and badge keys', async t => {
  moment.locale('es');
  const i18n = i18next.createInstance();
  await i18n.init({ lng: 'es', resources: { es: { translation: es } } });
  const onChange = t.mock.fn();
  const Component = load('../components/common/ChipDatePicker.jsx', {
    'react-i18next': translation,
    '@mui/x-date-pickers': { DatePicker: 'DatePicker', PickerDay: 'PickerDay' },
    '@mui/material': { Tooltip: 'Tooltip', Badge: 'Badge' },
  }).default;
  let tree;
  await act(async () => {
    tree = renderer.create(React.createElement(translation.I18nextProvider, { i18n }, React.createElement(Component, {
      date: '2026-10-21', onChange, badgedDates: { '21-10-2026': 2 },
    })));
  });
  t.after(() => tree.unmount());
  const picker = tree.root.findByType('DatePicker');
  assert.equal(picker.props.format, 'L');
  assert.equal(picker.props.value.format(picker.props.format), '21/10/2026');
  await act(async () => picker.props.onChange(moment('2026-11-04')));
  assert.equal(onChange.mock.calls[0].arguments[0], '2026-11-04');
  await act(async () => picker.props.onChange(null));
  assert.equal(onChange.mock.calls[1].arguments[0], null);
  const day = picker.props.slots.day({ day: moment('2026-10-21'), selected: false });
  assert.equal(day.props.title, '2 importaciones');
});

const deleteDialogProps = (path, context) => {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8');
  const ast = parseSync(source, options);
  let element;
  const visit = node => {
    if(!node || typeof node !== 'object') return;
    if(node.type === 'JSXElement' && node.openingElement.name.name === 'DeleteEntityDialog') element = node;
    for(const value of Object.values(node)) {
      if(Array.isArray(value)) value.forEach(visit);
      else if(value && typeof value === 'object') visit(value);
    }
  };
  visit(ast);
  assert.ok(element, 'Delete dialog must exist');
  const { code } = transformSync(`exports.default = () => (${source.slice(element.start, element.end)});`, options);
  const exports = {};
  vm.runInNewContext(code, { exports, React, DeleteEntityDialog: 'DeleteEntityDialog', ...context });
  return exports.default().props;
};

test('repository deletion labels are translated and preserve IDs and the submit callback', async t => {
  const i18n = i18next.createInstance();
  await i18n.init({ lng: 'es', resources: { es: { translation: es } } });
  const onDeleteRepo = t.mock.fn();
  for(const isCollection of [false, true]) {
    for(const version of [false, 'v1']) {
      const target = { short_code: 'Synthetic', version };
      const props = deleteDialogProps('../components/repos/RepoHome.jsx', {
        t: i18n.t.bind(i18n), isCollection, deleteTarget: target, deletingRepo: false,
        isVersionObject: value => Boolean(value.version), getTargetVersion: value => value,
        repo: { short_code: 'Synthetic' }, onDeleteRepo, setDeleteTarget: () => {},
      });
      assert.equal(props.entityType, version ? 'Versión del repositorio' : isCollection ? 'Colección' : 'Fuente');
      assert.equal(props.entityId, version ? 'Synthetic [v1]' : 'Synthetic');
      assert.equal(props.relationship, version ? '' : 'versiones, ');
      assert.equal(props.associationsLabel, 'conceptos y mapeos');
      assert.equal(props.onSubmit, onDeleteRepo);
    }
  }
  assert.equal(onDeleteRepo.mock.callCount(), 0);
});

test('organization deletion labels preserve the organization ID and submit callback', async t => {
  const i18n = i18next.createInstance();
  await i18n.init({ lng: 'es', resources: { es: { translation: es } } });
  const onDelete = t.mock.fn();
  const props = deleteDialogProps('../components/orgs/OrgHome.jsx', {
    t: i18n.t.bind(i18n), deleteOrg: true, org: { id: 'Synthetic' }, onDelete, setDeleteOrg: () => {},
  });
  assert.equal(props.entityType, 'Organización');
  assert.equal(props.entityId, 'Synthetic');
  assert.equal(props.relationship, '');
  assert.equal(props.associationsLabel, 'repositorios');
  assert.equal(props.onSubmit, onDelete);
  assert.equal(onDelete.mock.callCount(), 0);
});
