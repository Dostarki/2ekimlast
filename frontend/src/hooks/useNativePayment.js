import { useAccount, useWalletClient } from 'wagmi';
import { isAddress, numberToHex } from 'viem';
import { robinhoodMainnet } from '../lib/walletConfig';

export const nativePaymentRequest = (quote, address) => {
  if (quote?.chain_id !== robinhoodMainnet.id) throw new Error('Switch to Robinhood Chain Mainnet (4663).');
  if (quote.payment_mode !== 'native_transfer') throw new Error('Refresh this quote before paying.');
  if (Date.parse(quote.expires_at) <= Date.now()) throw new Error('Quote expired. Refresh before paying.');
  if (!isAddress(address) || !isAddress(quote.recipient) || BigInt(quote.amount_wei) <= 0n) throw new Error('Invalid payment quote.');
  // Robinhood internal accounts accept native value transfers without calldata.
  return { from: address, to: quote.recipient, value: numberToHex(BigInt(quote.amount_wei)), chainId: numberToHex(robinhoodMainnet.id) };
};

export const useNativePayment = () => {
  const { address, chainId } = useAccount();
  const { data: walletClient } = useWalletClient();
  const sendNativePayment = async (quote, expectedAddress) => {
    if (!walletClient || address?.toLowerCase() !== expectedAddress?.toLowerCase() || chainId !== robinhoodMainnet.id) {
      throw new Error('Connect the signed-in wallet on Robinhood Chain Mainnet (4663).');
    }
    const transaction = nativePaymentRequest(quote, expectedAddress);
    const activeChain = await walletClient.request({ method: 'eth_chainId' });
    if (Number(activeChain) !== robinhoodMainnet.id) throw new Error('Switch to Robinhood Chain Mainnet (4663).');
    // Standard wallet RPC only: no unsupported wallet_sendTransaction fallback,
    // no silent replacement charge, and no retry after an ambiguous result.
    try {
      return await walletClient.request({ method: 'eth_sendTransaction', params: [transaction] }, { retryCount: 0 });
    } catch (error) {
      const details = `${error.details || ''} ${error.message || ''}`;
      if (/insufficient funds|insufficient balance/i.test(details)) throw new Error('Insufficient ETH for this payment and network fees.');
      throw error;
    }
  };
  return { sendNativePayment };
};