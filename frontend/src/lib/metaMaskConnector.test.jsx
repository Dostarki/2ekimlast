describe('MetaMask provider and connector selection', () => {
  const original_env = { ...process.env };

  beforeEach(() => {
    jest.resetModules();
    process.env.REACT_APP_METAMASK_WALLET_LINK = 'https://metamask.app.link/wc';
    process.env.REACT_APP_METAMASK_DOWNLOAD_URL = 'https://metamask.io/download/';
    if (!global.window) global.window = {};
    delete global.window.ethereum;
  });

  afterEach(() => {
    jest.dontMock('./metaMaskProvider');
    jest.dontMock('@rainbow-me/rainbowkit');
    jest.dontMock('wagmi/connectors');
    jest.dontMock('wagmi');
    if (global.window) delete global.window.ethereum;
    process.env = { ...original_env };
  });

  it('getMetaMaskProvider filters impersonators and selects real provider from ethereum.providers', () => {
    const fake = { isMetaMask: true, isRabby: true, request: jest.fn() };
    const real = { isMetaMask: true, request: jest.fn(), on: jest.fn(), removeListener: jest.fn() };
    global.window.ethereum = { providers: [fake, real] };

    const { getMetaMaskProvider } = require('./metaMaskProvider');
    expect(getMetaMaskProvider()).toBe(real);
  });

  it('metaMaskInjectedWallet returns WalletConnect metadata when no injected provider exists', () => {
    jest.doMock('./metaMaskProvider', () => ({ getMetaMaskProvider: () => undefined }));
    const wcConnector = jest.fn(() => ({ id: 'walletconnect-connector' }));
    jest.doMock('@rainbow-me/rainbowkit', () => ({ getWalletConnectConnector: wcConnector }));
    jest.doMock('wagmi/connectors', () => ({ injected: jest.fn() }));
    jest.doMock('wagmi', () => ({ createConnector: jest.fn() }));

    const { metaMaskInjectedWallet } = require('./metaMaskInjectedWallet');
    const wallet = metaMaskInjectedWallet({ projectId: 'pid', walletConnectParameters: { metadata: { name: 'LastZHood' } } });

    expect(wallet.mobile).toBeDefined();
    expect(wallet.qrCode).toBeDefined();
    const rawUri = 'wc:abc123@2?relay-protocol=irn&symKey=s3cr3t';
    const deepLink = wallet.mobile.getUri(rawUri);
    expect(deepLink).toContain('https://metamask.app.link/wc?uri=');
    expect(decodeURIComponent(deepLink.split('uri=')[1])).toBe(rawUri);
    expect(wallet.qrCode.getUri(rawUri)).toBe(rawUri);
    expect(wallet.createConnector).toEqual({ id: 'walletconnect-connector' });
  });

  it('metaMaskInjectedWallet uses injected connector and exact selected provider when installed', () => {
    const chosen = { isMetaMask: true, request: jest.fn(), id: 'real-provider' };
    jest.doMock('./metaMaskProvider', () => ({ getMetaMaskProvider: () => chosen }));
    jest.doMock('@rainbow-me/rainbowkit', () => ({ getWalletConnectConnector: jest.fn() }));
    jest.doMock('wagmi/connectors', () => ({
      injected: opts => config => ({
        id: 'injected',
        provider: opts.target().provider,
        shimDisconnect: opts.shimDisconnect,
        cfg: config,
      }),
    }));
    jest.doMock('wagmi', () => ({ createConnector: factory => factory({ test: true }) }));

    const { metaMaskInjectedWallet } = require('./metaMaskInjectedWallet');
    const wallet = metaMaskInjectedWallet({ projectId: 'pid', walletConnectParameters: {} });
    const connector = wallet.createConnector({ id: 'wallet-details' });

    expect(wallet.mobile).toBeUndefined();
    expect(wallet.qrCode).toBeUndefined();
    expect(connector.provider).toBe(chosen);
    expect(connector.shimDisconnect).toBe(true);
  });
});
