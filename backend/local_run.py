"""Run DEADZONE locally with an in-memory MongoDB-compatible store.

This launcher is intentionally separate from ``server.py`` so production keeps
using its configured MongoDB connection. Account, progress, auth-session, market
order, delivery, mission, and economy-ledger collections are mirrored to the
local JSON persistence file; world/session state remains process-local.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
import bcrypt


# Load local settings first, then supply only values still absent from the
# process environment. This keeps explicit shell/CI configuration authoritative.
load_dotenv(Path(__file__).parent / ".env")
for key, value in {
    "MONGO_URL": "mongodb://local-memory",
    "DB_NAME": "deadzone_local",
    "CORS_ORIGINS": "http://localhost:3000",
    "ADMIN_ORIGIN": "http://localhost:3000",
    "ADMIN_PROXY_ORIGIN": "http://localhost:3000",
    "ADMIN_PASSWORD": "admin",
    "JWT_SECRET": "deadzone-local-dev-secret",
}.items():
    os.environ.setdefault(key, value)

# The production configuration normally supplies this value. Generate one only
# for local in-memory use so the included admin routes can complete startup.
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    bcrypt.hashpw(os.environ["ADMIN_PASSWORD"].encode(), bcrypt.gensalt()).decode(),
)

# server.py imports this symbol after the replacement below.  Only this local
# entry point gets the in-memory client; normal server.py execution is unchanged.
import motor.motor_asyncio
from mongomock_motor import AsyncMongoMockClient

motor.motor_asyncio.AsyncIOMotorClient = AsyncMongoMockClient

from server import app


if __name__ == "__main__":
    import uvicorn

    print("LastZHood local backend: account and commerce data persist locally; world/session state resets on exit.")
    uvicorn.run(app, host="127.0.0.1", port=8001)
