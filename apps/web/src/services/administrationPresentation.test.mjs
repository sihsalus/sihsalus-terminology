/* eslint-env node, es2020 */
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
const load = (file, overrides = {}) => {
  const filename = fileURLToPath(new URL(`../components/${file}.jsx`, import.meta.url));
  const {code} = transformFileSync(filename, {
    babelrc: false, configFile: false,
    presets: [['@babel/preset-env', {targets: {node: '22'}}], '@babel/preset-react'],
  });
  const exports = {};
  const modules = {
    react: React,
    'react-i18next': translation,
    '../../common/utils': {dropVersion: url => url, humanFileSize: size => `${size} B`, arrayToSentence: values => values.join(', ')},
    '../app/LayoutContext': {OperationsContext: React.createContext({setAlert() {}})},
    '@mui/material': Object.fromEntries(['TextField', 'CircularProgress', 'Divider', 'DialogContent', 'DialogActions', 'Button'].map(name => [name, name])),
    '@mui/icons-material': {CloudUpload: 'UploadIcon'},
    ...overrides,
  };
  vm.runInNewContext(code, {exports, require: name => {
    if (name in modules) return modules[name];
    if (name === 'lodash' || name.startsWith('lodash/')) return require(name);
    if (name.endsWith('.scss')) return {};
    if (name.startsWith('@mui/') || name.startsWith('../') || name.startsWith('./')) return name.split('/').at(-1);
    throw new Error(`Unexpected import ${name}`);
  }}, {filename});
  return exports.default;
};
const render = async (t, Component, props) => {
  const i18n = i18next.createInstance();
  await i18n.init({lng: 'es', resources: {es: {translation: es}}});
  let tree;
  await act(async () => {tree = renderer.create(React.createElement(translation.I18nextProvider, {i18n}, React.createElement(Component, props)));});
  t.after(() => tree.unmount());
  return tree;
};
const text = node => typeof node === 'string' ? node : Array.isArray(node) ? node.map(text).join('') : (node?.children || []).map(text).join('');

test('Spanish cascade labels preserve API method and mapping codes', async t => {
  const onChange = t.mock.fn();
  const tree = await render(t, load('common/CascadeSelector'), {onChange});
  const preset = tree.root.findAllByType('Select').find(select => select.props.value === 'none');
  assert.equal(preset.props.label, 'Cascada');
  await act(async () => preset.props.onChange({target: {value: 'sourcetoconcepts'}}));
  assert.deepEqual(JSON.parse(JSON.stringify(onChange.mock.calls.at(-1).arguments[0])), {
    method: 'sourcetoconcepts', mapTypes: 'Q-AND-A,CONCEPT-SET', cascadeLevels: '*', returnMapTypes: '*',
  });
  await act(async () => preset.props.onChange({target: {value: 'custom'}}));
  const field = tree.root.findAllByType('TextField').find(field => field.props.label === 'Tipos de mapeo');
  await act(async () => field.props.onChange({target: {value: 'SAME-AS'}}));
  assert.equal(onChange.mock.calls.at(-1).arguments[0].mapTypes, 'SAME-AS');
  await act(async () => tree.root.findByType('FormControlLabel').props.control.props.onChange({target: {checked: true}}));
  assert.equal(onChange.mock.calls.at(-1).arguments[0].transformReferences, 'openmrs_concept_reference');
});

test('file upload guidance and native rejection reasons use Spanish', async t => {
  let nativeOptions;
  const Component = load('common/FileUploader', {'react-dropzone': {useDropzone: options => {
    nativeOptions = options;
    return {
      acceptedFiles: [{path: 'synthetic.csv', size: 20}],
      fileRejections: [{file: {path: 'oversize.csv', size: 5000}, errors: [{code: 'file-too-large', message: 'File is too large'}]}],
      getRootProps: props => props, getInputProps: () => ({}),
    };
  }}});
  const accept = {'text/csv': ['.csv']};
  const tree = await render(t, Component, {accept, maxSize: 4096, maxFiles: 2});
  const rendered = text(tree.toJSON());
  assert.ok(rendered.includes('Arrastra un archivo aquí o haz clic para seleccionarlo'));
  assert.ok(rendered.includes('Formatos admitidos: csv'));
  assert.ok(rendered.includes('El archivo supera el tamaño máximo de 4096 B.'));
  assert.ok(rendered.includes('synthetic.csv'));
  assert.equal(nativeOptions.accept, accept);
  assert.equal(nativeOptions.maxSize, 4096);
  assert.equal(nativeOptions.maxFiles, 2);
});

test('member picker uses Spanish and preserves member identity', async t => {
  const member = {username: 'synthetic', name: 'Original Name'};
  const tree = await render(t, load('orgs/EditMembers'), {org: {name: 'SIHSALUS'}, members: [member]});
  const picker = tree.root.findByType('Autocomplete');
  assert.equal(picker.props.noOptionsText, 'Escribe al menos 2 caracteres para buscar');
  assert.equal(picker.props.renderInput({}).props.label, 'Miembros');
  assert.equal(picker.props.value[0], member);
  assert.equal(picker.props.getOptionLabel(member), 'synthetic (Original Name)');
});

for (const source of ['Original & Source', undefined]) {
  test(`collection description preserves concept text with source=${Boolean(source)}`, async t => {
    const concept = {id: 'synthetic', display_name: 'Original < 10 & value', url: '/orgs/test/sources/test/concepts/synthetic/', source};
    const tree = await render(t, load('common/AddToCollectionDialog'), {open: false, concept});
    const expected = source ? 'Se agregará: Original < 10 & value de Original & Source' : 'Se agregará: Original < 10 & value';
    assert.ok(text(tree.toJSON()).includes(expected));
    assert.equal(concept.display_name, 'Original < 10 & value');
  });
}
