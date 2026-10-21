/* eslint-env node, es2020 */
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { transformFileSync } from '@babel/core';
import React from 'react';
import renderer, { act } from 'react-test-renderer';

const loadControls = (authenticated, enabled) => {
  const filename = fileURLToPath(new URL('../components/app/HeaderControls.jsx', import.meta.url));
  const { code } = transformFileSync(filename, {
    babelrc: false, configFile: false,
    presets: [['@babel/preset-env', {targets: {node: '22'}}], '@babel/preset-react'],
  });
  const exports = {};
  const modules = {
    react: React,
    'react-i18next': {useTranslation: () => ({t: key => key})},
    '../../common/utils': {isLoggedIn: () => authenticated, isSelfRegistrationEnabled: () => enabled},
    '@mui/material/Box': 'Box',
    '@mui/material/Button': 'Button',
    '@mui/material/IconButton': 'IconButton',
    '@mui/icons-material/Add': 'AddIcon',
    '@mui/icons-material/Publish': 'ImportIcon',
    '../users/UserMenu': 'UserMenu',
    '../users/UserProfileButton': 'UserProfileButton',
    '../users/AddMenuList': 'AddMenuList',
  };
  vm.runInNewContext(code, {
    exports, window: {location: {href: 'https://terminology.example/#/search/?q=demo'}},
    require: name => { assert.ok(name in modules, `Unexpected import ${name}`); return modules[name]; },
  }, {filename});
  return exports.default;
};

for(const [authenticated, enabled] of [[false, true], [false, false], [true, true], [true, false]]) {
  test(`header registration honors authenticated=${authenticated}, enabled=${enabled}`, async t => {
    let tree;
    await act(async () => { tree = renderer.create(React.createElement(loadControls(authenticated, enabled))); });
    t.after(() => tree.unmount());
    const buttons = tree.root.findAllByType('Button');
    const register = buttons.filter(button => button.props.href === '#/signup');
    assert.equal(register.length, !authenticated && enabled ? 1 : 0);
    const login = buttons.filter(button => button.props.children === 'auth.sign_in');
    assert.equal(login.length, authenticated ? 0 : 1);
    if(!authenticated) {
      assert.equal(decodeURIComponent(login[0].props.href.split('returnTo=')[1]), 'https://terminology.example/#/search/?q=demo');
      if(enabled) assert.equal(register[0].props.variant, 'contained');
    }
    assert.equal(tree.root.findAllByType('AddMenuList').length, authenticated ? 1 : 0);
    const profile = tree.root.findByType('UserProfileButton');
    assert.equal(profile.props['aria-label'], 'common.account_menu');
    assert.equal(profile.props['aria-expanded'], false);
    await act(async () => profile.props.onClick());
    assert.equal(tree.root.findByType('UserMenu').props.isOpen, true);
  });
}
