import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import DocsPage from './DocsPage';

jest.mock('react-router-dom', () => {
  global.TextEncoder = require('util').TextEncoder;
  global.TextDecoder = require('util').TextDecoder;
  return require('../../node_modules/react-router/dist/development/index.js');
}, { virtual: true });
jest.mock('@/lib/utils', () => ({ cn: (...values) => values.filter(Boolean).join(' ') }), { virtual: true });
global.IS_REACT_ACT_ENVIRONMENT = true;

describe('public field guide', () => {
  let host, root;
  beforeEach(() => {
    host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host);
    window.scrollTo = jest.fn(); HTMLElement.prototype.scrollIntoView = jest.fn();
  });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
  const mount = async (url = '/docs') => act(async () => root.render(<MemoryRouter initialEntries={[url]}><DocsPage /></MemoryRouter>));
  test('opens a direct chapter link and falls back from an unknown chapter', async () => {
    await mount('/docs?chapter=market#luck-box-odds');
    expect(host.querySelector('h1').textContent).toBe('Market, VIP & Economy');
    expect(host.querySelector('#luck-box-odds')).not.toBeNull();
    expect(host.querySelector('[aria-current="page"]').textContent).toContain('Market');
  });
  test('search result navigates to an instruction and clears the query', async () => {
    await mount();
    const input = host.querySelector('input');
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, 'medkit');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const result = [...host.querySelectorAll('.docs-results a')].find(a => a.textContent.includes('Healing supplies'));
    expect(result).toBeTruthy();
    await act(async () => result.click());
    expect(host.querySelector('h1').textContent).toBe('Combat & Safe Zones');
    expect(input.value).toBe('');
    expect(host.querySelector('.docs-results')).toBeNull();
  });
  test('mobile chapter dialog provides named navigation and closes after selection', async () => {
    await mount('/docs?chapter=unknown');
    expect(host.querySelector('h1').textContent).toBe('First Five Minutes');
    await act(async () => host.querySelector('.docs-menu-button').click());
    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog.textContent).toContain('Field Guide chapters');
    await act(async () => [...dialog.querySelectorAll('a')].find(a => a.textContent.includes('Soldiers & Missions')).click());
    expect(host.querySelector('h1').textContent).toBe('Soldiers & Missions');
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  });
});
