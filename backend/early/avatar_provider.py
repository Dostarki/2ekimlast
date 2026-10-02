"""Keyless public profile metadata. No account ownership or identity verification."""
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

BASE = os.environ['FXTWITTER_BASE_URL'].rstrip('/')
UA = os.environ['FXTWITTER_USER_AGENT']
TIMEOUT = float(os.environ['X_LOOKUP_TIMEOUT_SECONDS'])
TTL = int(os.environ['X_AVATAR_CACHE_SECONDS'])
FAILURE_TTL = int(os.environ['X_AVATAR_FAILURE_CACHE_SECONDS'])
MAX_BYTES = int(os.environ['X_AVATAR_MAX_BYTES'])
CDN_HOSTS = set(os.environ['X_AVATAR_CDN_HOSTS'].split(','))
_inflight = {}


def safe_avatar_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        url = urlparse(value)
        if (url.scheme != 'https' or url.hostname not in CDN_HOSTS or
                url.port not in (None, 443) or url.username or url.password or
                not url.path.startswith('/profile_images/') or url.query or url.fragment):
            return None
        return value
    except ValueError:
        return None


async def limited_body(client, url, limit, accept):
    async with client.stream('GET', url, headers={'User-Agent': UA, 'Accept': accept}, follow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError('Unexpected provider response')
        if int(response.headers.get('content-length', 0)) > limit:
            raise ValueError('Response too large')
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > limit:
                raise ValueError('Response too large')
        return bytes(body), response.headers.get('content-type', '').split(';')[0].lower()


async def _resolve(handle, db, client):
    now = datetime.now(timezone.utc)
    old = await db.x_avatar_metadata.find_one({'handle': handle, 'expires_at': {'$gt': now}}, {'_id': 0})
    if old:
        # Recheck cached URLs as well; never trust a database value as a proxy target.
        return safe_avatar_url(old.get('avatar_url'))
    avatar_url = None
    try:
        raw, content_type = await asyncio.wait_for(
            limited_body(client, f'{BASE}/2/profile/{handle}', 262144, 'application/json'), TIMEOUT)
        if content_type != 'application/json':
            raise ValueError('Unexpected metadata content type')
        data = json.loads(raw)
        user = data.get('user') or {}
        if (data.get('code') == 200 and user.get('protected') is not True and
                str(user.get('screen_name', '')).lower() == handle):
            avatar_url = safe_avatar_url(user.get('avatar_url'))
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, asyncio.TimeoutError):
        logging.info('Public X avatar metadata unavailable')
    await db.x_avatar_metadata.update_one({'handle': handle}, {'$set': {
        'handle': handle, 'avatar_url': avatar_url,
        'source': 'fxtwitter' if avatar_url else None,
        'expires_at': now + timedelta(seconds=TTL if avatar_url else FAILURE_TTL),
    }}, upsert=True)
    return avatar_url


async def lookup_avatar(handle, db, client):
    # A profile request and card/operator image requests share one upstream lookup.
    if handle not in _inflight:
        _inflight[handle] = asyncio.create_task(_resolve(handle, db, client))
    task = _inflight[handle]
    try:
        return await asyncio.shield(task)
    finally:
        if task.done() and _inflight.get(handle) is task:
            _inflight.pop(handle, None)


def avatar_candidates(url):
    large = re.sub(r'_normal(?=\.[^./]+$)', '_400x400', url)
    return list(dict.fromkeys([large, url]))