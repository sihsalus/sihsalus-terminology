/* eslint-env node, es2020 */
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { transformFileSync } from '@babel/core';
import React from 'react';
import renderer, { act } from 'react-test-renderer';

// Exercise real React state; replace network, translation and visual dependencies only.
const load = (file, api = {}, utils = {}) => {
  const filename = fileURLToPath(new URL(`../components/${file}.jsx`, import.meta.url));
  const { code } = transformFileSync(filename, {
    babelrc: false, configFile: false,
    presets: [['@babel/preset-env', { targets: { node: '22' } }], '@babel/preset-react'],
  });
  const exports = {};
  const window = { location: { href: '' } };
  const modules = {
    react: React,
    'react-i18next': { useTranslation: () => ({ t: key => key }) },
    '@mui/material': Object.fromEntries(['Alert', 'Box', 'Button', 'TextField', 'Typography'].map(name => [name, name])),
    '../../services/APIService': api,
    '../../common/utils': utils,
    '../users/LocalSignup': 'LocalSignup',
    '../users/LocalSignIn': 'LocalSignIn',
  };
  vm.runInNewContext(code, { exports, window, URLSearchParams, require: name => {
    assert.ok(name in modules, `Unexpected import ${name}`);
    return modules[name];
  } }, { filename });
  return { Component: exports.default, window };
};
const render = async (Component, props) => {
  let tree;
  await act(async () => { tree = renderer.create(React.createElement(Component, props)); });
  return tree;
};
const click = async button => act(async () => { await button.props.onClick(); });
const submit = async tree => act(async () => { await tree.root.findByType('Box').props.onSubmit({ preventDefault() {} }); });

test('local signup posts anonymous credentials then asks for email confirmation', async t => {
  const request = t.mock.fn(async () => ({ status: 201 }));
  const api = { users: () => ({ signup: () => ({ request }) }) };
  const { Component } = load('users/LocalSignup', api);
  const tree = await render(Component);
  t.after(() => tree.unmount());
  const fields = { username: 'synthetic', email: 'synthetic@pucp.edu.pe', password: 'synthetic-password-91' };
  for(const field of tree.root.findAllByType('TextField'))
    await act(async () => field.props.onChange({ target: { value: fields[field.props.name] } }));
  await submit(tree);
  const [method, data, token] = request.mock.calls[0].arguments;
  assert.equal(method, 'POST');
  assert.deepEqual(JSON.parse(JSON.stringify(data)), fields);
  assert.equal(token, false);
  assert.equal(tree.root.findByType('Alert').props.children, 'auth.signup_check_email');
  assert.equal(tree.root.findAllByType('TextField').length, 0);
});

test('local signup shows server field errors and clears the password', async t => {
  const api = { users: () => ({ signup: () => ({ request: async () => {
    throw { response: { status: 400, data: { email: ['Institution required'] } } };
  } }) }) };
  const { Component } = load('users/LocalSignup', api);
  const tree = await render(Component);
  t.after(() => tree.unmount());
  await submit(tree);
  const fields = tree.root.findAllByType('TextField');
  assert.equal(fields.find(field => field.props.name === 'email').props.helperText, 'Institution required');
  assert.equal(fields.find(field => field.props.name === 'password').props.value, '');
});

test('email verification waits for explicit confirmation and uses the native API', async t => {
  const request = t.mock.fn(async () => ({ status: 200 }));
  const verify = t.mock.fn(() => ({ request }));
  const users = t.mock.fn(() => ({ verify }));
  const { Component } = load('users/LocalEmailVerification', { users });
  const tree = await render(Component, { match: { params: { username: 'synthetic', token: 'token/value' } } });
  t.after(() => tree.unmount());
  assert.equal(request.mock.callCount(), 0);
  await click(tree.root.findAllByType('Button')[0]);
  assert.equal(users.mock.calls[0].arguments[0], 'synthetic');
  assert.equal(verify.mock.calls[0].arguments[0], 'token%2Fvalue');
  assert.equal(request.mock.calls[0].arguments[0], 'GET');
  assert.equal(request.mock.calls[0].arguments[2], false);
  assert.equal(tree.root.findByType('Alert').props.children, 'auth.email_verified_sign_in');
});

test('a rejected verification link does not report success', async t => {
  const api = { users: () => ({ verify: () => ({ request: async () => { throw new Error('Invalid link'); } }) }) };
  const { Component } = load('users/LocalEmailVerification', api);
  const tree = await render(Component, { match: { params: { username: 'synthetic', token: 'wrong' } } });
  t.after(() => tree.unmount());
  await click(tree.root.findAllByType('Button')[0]);
  assert.equal(tree.root.findByType('Alert').props.children, 'auth.verify_email_error');
});

for(const [enabled, sso] of [[false, false], [true, false], [true, true]]) {
  test(`signup route honors registration=${enabled} and SSO=${sso}`, async t => {
    const getRegisterURL = t.mock.fn(async () => 'https://identity.example.test/register');
    const { Component, window } = load('app/SignupRedirect', {}, {
      isSelfRegistrationEnabled: () => enabled, isSSOConfigured: () => sso, getRegisterURL,
    });
    const tree = await render(Component);
    t.after(() => tree.unmount());
    assert.equal(tree.root.findAllByType('LocalSignup').length, enabled && !sso ? 1 : 0);
    assert.equal(getRegisterURL.mock.callCount(), enabled && sso ? 1 : 0);
    assert.equal(window.location.href, enabled && sso ? 'https://identity.example.test/register' : '');
  });
}

test('unverified local login explains email confirmation and offers registration', async t => {
  const api = { users: () => ({ login: () => ({ request: async () => {
    throw { response: { status: 401, data: { email: 'synthetic@pucp.edu.pe' } } };
  } }) }) };
  const { Component } = load('users/LocalSignIn', api, { isSelfRegistrationEnabled: () => true });
  const tree = await render(Component);
  t.after(() => tree.unmount());
  await submit(tree);
  assert.equal(tree.root.findByType('Alert').props.children, 'auth.signup_check_email');
  assert.ok(tree.root.findAllByType('Button').some(button => button.props.href === '#/signup'));
});

test('signup redirect exposes a translated retry after an SSO URL failure', async t => {
  let calls = 0;
  const { Component, window } = load('app/SignupRedirect', {}, {
    isSelfRegistrationEnabled: () => true,
    isSSOConfigured: () => true,
    getRegisterURL: async () => {
      calls++;
      if(calls === 1) throw new Error('Synthetic browser failure');
      return 'https://identity.example.test/register';
    },
  });
  const tree = await render(Component);
  t.after(() => tree.unmount());
  assert.equal(tree.root.findByType('Alert').props.children, 'auth.redirect_failed');
  await act(async () => tree.root.findByType('Alert').props.action.props.onClick());
  assert.equal(calls, 2);
  assert.equal(window.location.href, 'https://identity.example.test/register');
});

test('sign-in redirect preserves returnTo and translates its pending state', async t => {
  const getLoginURL = t.mock.fn(async () => 'https://identity.example.test/login');
  const { Component, window } = load('app/SigninRedirect', {}, {
    isSSOConfigured: () => true, getLoginURL,
  });
  const tree = await render(Component, {location: {search: '?returnTo=https%3A%2F%2Fterminology.example%2F%23%2Fsearch'}});
  t.after(() => tree.unmount());
  assert.equal(getLoginURL.mock.calls[0].arguments[0], 'https://terminology.example/#/search');
  assert.equal(window.location.href, 'https://identity.example.test/login');
  assert.equal(tree.root.findByType('h4').props.children, 'auth.redirecting');
});

for(const search of ['', '?returnTo=https%3A%2F%2Fterminology.example%2F%23%2Fsearch%2F%3Fq%3Ddemo']) {
  test(`local sign-in prepares an explicit return route only: ${Boolean(search)}`, async t => {
    const getLoginURL = t.mock.fn(async () => 'https://terminology.example/#/signin');
    const { Component, window } = load('app/SigninRedirect', {}, {
      isSSOConfigured: () => false, getLoginURL,
    });
    const tree = await render(Component, {location: {search}});
    t.after(() => tree.unmount());
    assert.equal(tree.root.findAllByType('LocalSignIn').length, 1);
    assert.equal(window.location.href, '');
    assert.equal(getLoginURL.mock.callCount(), search ? 1 : 0);
    if(search) assert.equal(getLoginURL.mock.calls[0].arguments[0], 'https://terminology.example/#/search/?q=demo');
  });
}
