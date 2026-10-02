import { createContext, useContext } from 'react';
import { useAccessCheckout } from '../hooks/useAccessCheckout';

const AccessCheckoutContext = createContext(null);
export const AccessCheckoutProvider = ({ children }) => {
  const checkout = useAccessCheckout();
  return <AccessCheckoutContext.Provider value={checkout}>{children}</AccessCheckoutContext.Provider>;
};
export const useAccessPayment = () => useContext(AccessCheckoutContext);