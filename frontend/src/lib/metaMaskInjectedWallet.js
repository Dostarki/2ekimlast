import { getWalletConnectConnector } from '@rainbow-me/rainbowkit';
import { createConnector } from 'wagmi';
import { injected } from 'wagmi/connectors';
import { getMetaMaskProvider } from './metaMaskProvider';

const walletLink = process.env.REACT_APP_METAMASK_WALLET_LINK;
const downloadUrl = process.env.REACT_APP_METAMASK_DOWNLOAD_URL;
if (!walletLink || !downloadUrl) throw new Error('Missing MetaMask connection URLs.');

// Keep RainbowKit's chooser/WalletConnect metadata without initializing the
// MetaMask SDK, whose analytics module crashes CRA at import time.
export const metaMaskInjectedWallet = ({ projectId, walletConnectParameters }) => {
  const installed = !!getMetaMaskProvider();
  const getUri = uri => `${walletLink}?uri=${encodeURIComponent(uri)}`;
  return {
    id: 'metaMask',
    name: 'MetaMask',
    rdns: 'io.metamask',
    iconUrl: '/images/metamask.svg',
    iconBackground: '#ffffff',
    installed: installed || undefined,
    downloadUrls: { browserExtension: downloadUrl, mobile: downloadUrl },
    mobile: installed ? undefined : { getUri },
    qrCode: installed ? undefined : { getUri: uri => uri },
    createConnector: installed
      ? walletDetails => createConnector(config => ({
          ...injected({
            target: () => ({ id: 'metaMask', name: 'MetaMask', provider: getMetaMaskProvider() }),
            shimDisconnect: true,
          })(config),
          ...walletDetails,
        }))
      : getWalletConnectConnector({ projectId, walletConnectParameters }),
  };
};