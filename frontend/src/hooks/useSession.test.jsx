import { act } from 'react';
import { createRoot } from 'react-dom/client';
import React from 'react';

// TEST-ONLY MOCKS: isolates hook behavior from network worker/runtime audio.
let mockCurrentWorker = null;
const mockAudio = {
  init: jest.fn(() => Promise.resolve()),
  stopAutomatic: jest.fn(),
  stopEnemies: jest.fn(),
  enemies: jest.fn(),
  explosion: jest.fn(),
  shot: jest.fn(),
  supply: jest.fn(),
};

jest.mock('../game/createNetworkWorker', () => ({
  createNetworkWorker: () => mockCurrentWorker,
}));
jest.mock('../game/audio', () => ({ audio: mockAudio }));
jest.mock('sonner', () => ({ toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() } }));

process.env.REACT_APP_BACKEND_URL = 'https://zone-trade.preview.emergentagent.com';
const { useSession } = require('./useSession');

const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });

function Harness({ engineRef, onValue }) {
  const session = useSession(engineRef);
  onValue(session);
  return null;
}

function makeWorker() {
  return {
    onmessage: null,
    onerror: null,
    postMessage: jest.fn(),
    terminate: jest.fn(),
  };
}

describe('useSession critical hook matrix', () => {
  let container;
  let root;
  let latest;
  let engineRef;
  let original_url;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.useFakeTimers();
    localStorage.clear();
    original_url = global.URL;
    global.URL = class MockURL {
      constructor(base) {
        this.protocol = String(base || '').startsWith('https') ? 'https:' : 'http:';
        this.pathname = '/';
      }
      toString() {
        return `${this.protocol === 'https:' ? 'wss:' : 'ws:'}//example.test${this.pathname}`;
      }
    };
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    latest = null;
    engineRef = {
      current: {
        getInput: jest.fn(() => ({ type: 'input', x: 0, z: 0, fire: false })),
        movement: { noteInput: jest.fn() },
        receive: jest.fn(),
        setMode: jest.fn(),
        publishInput: null,
      },
    };
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: async () => ({ token: 'token-1' }) }));
    mockCurrentWorker = null;
    Object.values(mockAudio).forEach(fn => fn.mockClear && fn.mockClear());
    mockAudio.init.mockImplementation(() => Promise.resolve());
    act(() => root.render(<Harness engineRef={engineRef} onValue={v => { latest = v; }} />));
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    global.URL = original_url;
    jest.useRealTimers();
  });

  it('does not enter playing on open alone; enters on first state', async () => {
    const worker = makeWorker();
    mockCurrentWorker = worker;

    await act(async () => { await latest.start('TEST', 'glock18', 'soldier'); });
    expect(latest.mode).toBe('connecting');

    act(() => worker.onmessage({ data: { type: 'open' } }));
    expect(latest.mode).toBe('connecting');

    act(() => worker.onmessage({ data: { type: 'state', me: { id: 'p1', x: 0, z: 0 }, events: [] } }));
    expect(latest.mode).toBe('playing');
    expect(engineRef.current.setMode).toHaveBeenCalledWith('playing', 'glock18', 'soldier');
  });

  it('returns to lobby after 15s no-state timeout, and cleans worker', async () => {
    const worker = makeWorker();
    mockCurrentWorker = worker;

    await act(async () => { await latest.start('TEST', 'glock18', 'soldier'); });
    act(() => worker.onmessage({ data: { type: 'open' } }));
    act(() => worker.onmessage({ data: { type: 'ping', value: 31 } }));

    act(() => { jest.advanceTimersByTime(15100); });
    await flush();
    expect(latest.mode).toBe('lobby');
    expect(latest.error).toContain('No game data received');
    expect(worker.postMessage).toHaveBeenCalledWith({ type: 'disconnect' });

    act(() => { jest.advanceTimersByTime(350); });
    expect(worker.terminate).toHaveBeenCalled();
  });

  it('playing session with later no-state window also falls back to lobby', async () => {
    const worker = makeWorker();
    mockCurrentWorker = worker;

    await act(async () => { await latest.start('TEST', 'glock18', 'soldier'); });
    act(() => worker.onmessage({ data: { type: 'open' } }));
    act(() => worker.onmessage({ data: { type: 'state', me: { id: 'p1', x: 0, z: 0 }, events: [] } }));
    expect(latest.mode).toBe('playing');

    act(() => { jest.advanceTimersByTime(15100); });
    await flush();
    expect(latest.mode).toBe('lobby');
  });

  it('aborts stalled join and late response cannot resurrect the attempt', async () => {
    let resolveJoin;
    global.fetch = jest.fn(() => new Promise(resolve => { resolveJoin = resolve; }));
    const worker = makeWorker();
    mockCurrentWorker = worker;

    act(() => { latest.start('TEST', 'glock18', 'soldier'); });
    act(() => { latest.leave(); });
    expect(latest.mode).toBe('lobby');

    await act(async () => {
      resolveJoin({ ok: true, json: async () => ({ token: 'late-token' }) });
      await Promise.resolve();
    });
    expect(worker.onmessage).toBe(null);
    expect(latest.mode).toBe('lobby');
  });

  it('audio init rejection or unresolved promise never blocks successful start', async () => {
    const workerA = makeWorker();
    mockCurrentWorker = workerA;
    mockAudio.init.mockImplementationOnce(() => Promise.reject(new Error('audio denied')));

    await act(async () => { await latest.start('TEST', 'glock18', 'soldier'); });
    act(() => workerA.onmessage({ data: { type: 'open' } }));
    act(() => workerA.onmessage({ data: { type: 'state', me: { id: 'p1', x: 0, z: 0 }, events: [] } }));
    expect(latest.mode).toBe('playing');

    act(() => latest.leave());
    expect(latest.mode).toBe('lobby');

    const workerB = makeWorker();
    mockCurrentWorker = workerB;
    mockAudio.init.mockImplementationOnce(() => new Promise(() => {}));
    await act(async () => { await latest.start('TEST', 'glock18', 'soldier'); });
    act(() => workerB.onmessage({ data: { type: 'open' } }));
    act(() => workerB.onmessage({ data: { type: 'state', me: { id: 'p2', x: 0, z: 0 }, events: [] } }));
    expect(latest.mode).toBe('playing');
  });

  it('unmount runs teardown and clears active worker timers', async () => {
    const worker = makeWorker();
    mockCurrentWorker = worker;
    await act(async () => { await latest.start('TEST', 'glock18', 'soldier'); });
    act(() => worker.onmessage({ data: { type: 'open' } }));
    act(() => worker.onmessage({ data: { type: 'state', me: { id: 'p9', x: 0, z: 0 }, events: [] } }));

    act(() => root.unmount());
    act(() => { jest.advanceTimersByTime(350); });
    expect(worker.postMessage).toHaveBeenCalledWith({ type: 'disconnect' });
    expect(worker.terminate).toHaveBeenCalled();
  });
});
