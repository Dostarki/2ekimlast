"""Shared, mainnet-only network settings for authentication and ETH payments."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')
CHAIN_ID = int(os.environ['ROBINHOOD_CHAIN_ID'])
RPC_URL = os.environ['ROBINHOOD_RPC_URL']
if CHAIN_ID != 4663 or not RPC_URL.startswith('https://'):
    raise RuntimeError('Robinhood Mainnet (4663) and an HTTPS RPC are required.')