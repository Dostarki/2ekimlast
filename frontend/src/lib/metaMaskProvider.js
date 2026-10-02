// Keep this aligned with RainbowKit's MetaMask provider exclusions.
const OTHER_WALLET_FLAGS = [
  'isApexWallet', 'isAvalanche', 'isBackpack', 'isBifrost', 'isBitKeep',
  'isBitski', 'isBinance', 'isBlockWallet', 'isCoinbaseWallet', 'isDawn',
  'isEnkrypt', 'isExodus', 'isFrame', 'isFrontier', 'isGamestop', 'isHyperPay',
  'isImToken', 'isKuCoinWallet', 'isMathWallet', 'isNestWallet', 'isOkxWallet',
  'isOKExWallet', 'isOneInchIOSWallet', 'isOneInchAndroidWallet', 'isOpera',
  'isPhantom', 'isZilPay', 'isPortal', 'isxPortal', 'isRabby', 'isRainbow',
  'isStatus', 'isTalisman', 'isTally', 'isTokenPocket', 'isTokenary', 'isTrust',
  'isTrustWallet', 'isCTRL', 'isZeal', 'isCoin98', 'isMEWwallet', 'isSafeheron',
  'isSafePal', 'isWigwam', 'isZerion', '__seif',
];

export const isMetaMaskProvider = provider => {
  if (!provider?.isMetaMask || typeof provider.request !== 'function') return false;
  if (provider.isBraveWallet && !provider._events && !provider._state) return false;
  return !OTHER_WALLET_FLAGS.some(flag => provider[flag]);
};

export const getMetaMaskProvider = () => {
  if (typeof window === 'undefined') return undefined;
  const ethereum = window.ethereum;
  const providers = Array.isArray(ethereum?.providers) ? [...ethereum.providers, ethereum] : [ethereum];
  return providers.find(isMetaMaskProvider);
};