import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WagmiProvider } from "wagmi";
import { RainbowKitProvider, darkTheme } from "@rainbow-me/rainbowkit";
import "@rainbow-me/rainbowkit/styles.css";

import "@/index.css";
import App from "@/App";
import { AccessCheckoutProvider } from './lib/accessCheckoutContext';
import { wagmiConfig, robinhoodMainnet } from "@/lib/walletConfig";
import { AuthProvider } from "@/lib/authContext";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const deadzoneRainbowTheme = darkTheme({
  accentColor: "#c8d6a0",
  accentColorForeground: "#0f1712",
  borderRadius: "small",
  fontStack: "system",
  overlayBlur: "small",
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <WagmiProvider config={wagmiConfig}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RainbowKitProvider theme={deadzoneRainbowTheme} modalSize="compact" initialChain={robinhoodMainnet}>
            <AccessCheckoutProvider><App /></AccessCheckoutProvider>
          </RainbowKitProvider>
        </AuthProvider>
      </QueryClientProvider>
    </WagmiProvider>
  </React.StrictMode>,
);

