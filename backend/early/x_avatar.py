"""CORS-safe transient image proxy; MongoDB stores metadata, never image bytes."""
import asyncio
import io
import os
import re
import time
import warnings
from collections import OrderedDict, deque
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from PIL import Image, ImageOps
from pydantic import BaseModel

from .avatar_provider import MAX_BYTES, TIMEOUT, TTL, avatar_candidates, limited_body, lookup_avatar

router = APIRouter(prefix='/x', tags=['public-x-photo'])
_requests = OrderedDict()
_images = OrderedDict()
_image_inflight = {}
RATE_LIMIT = int(os.environ['X_LOOKUP_RATE_LIMIT'])


class XProfile(BaseModel):
    handle: str
    status: Literal['available', 'unavailable']
    avatar_path: str | None = None
    source: Literal['fxtwitter'] | None = None
    ownership_verified: Literal[False] = False


def clean_handle(raw):
    handle = raw.strip().removeprefix('@').lower()
    if not re.fullmatch(r'[a-z0-9_]{1,15}', handle):
        raise HTTPException(422, 'Use a valid X username.')
    return handle


def check_rate(request):
    key = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    history = _requests.setdefault(key, deque())
    while history and history[0] < now - 60:
        history.popleft()
    if len(history) >= RATE_LIMIT:
        raise HTTPException(429, 'Photo lookup is temporarily busy. Please try again later.', headers={'Retry-After': '60'})
    history.append(now)
    _requests.move_to_end(key)
    while len(_requests) > 2048:
        _requests.popitem(last=False)


def sanitize_image(raw):
    # Decode/re-encode only raster images. Reject SVG/HTML, decompression bombs,
    # oversized dimensions and corrupted payloads, and discard source metadata.
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as probe:
            if probe.format not in {'JPEG', 'PNG', 'WEBP'} or max(probe.size) > 4096:
                raise ValueError('Unsupported avatar image')
            probe.verify()
        with Image.open(io.BytesIO(raw)) as original:
            image = ImageOps.exif_transpose(original).convert('RGB')
            image.thumbnail((512, 512))
            output = io.BytesIO()
            image.save(output, format='PNG', optimize=True)
            return output.getvalue()


async def fetch_image(url, client):
    for candidate in avatar_candidates(url):
        try:
            raw, content_type = await limited_body(client, candidate, MAX_BYTES, 'image/png,image/jpeg,image/webp')
            if content_type not in {'image/png', 'image/jpeg', 'image/webp'}:
                raise ValueError('Unsupported content type')
            return await asyncio.to_thread(sanitize_image, raw)
        except (httpx.HTTPError, ValueError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            continue
    raise ValueError('Avatar unavailable')


@router.get('/profile/{raw_handle}', response_model=XProfile)
async def profile(raw_handle: str, request: Request):
    handle = clean_handle(raw_handle)
    check_rate(request)
    url = await lookup_avatar(handle, request.app.state.db, request.app.state.x_http)
    return XProfile(handle=handle, status='available' if url else 'unavailable',
                    avatar_path=f'/api/early/x/avatar/{handle}' if url else None,
                    source='fxtwitter' if url else None)


@router.get('/avatar/{raw_handle}')
async def avatar(raw_handle: str, request: Request):
    handle = clean_handle(raw_handle)
    check_rate(request)
    url = await lookup_avatar(handle, request.app.state.db, request.app.state.x_http)
    if not url:
        raise HTTPException(404, 'Public profile photo unavailable.', headers={'Cache-Control': 'no-store'})
    cached = _images.get(url)
    cache_hit = bool(cached and cached[0] > time.monotonic())
    if cache_hit:
        image = cached[1]
        _images.move_to_end(url)
    else:
        if url not in _image_inflight:
            _image_inflight[url] = asyncio.create_task(asyncio.wait_for(fetch_image(url, request.app.state.x_http), TIMEOUT))
        task = _image_inflight[url]
        try:
            image = await asyncio.shield(task)
        except (httpx.HTTPError, ValueError, OSError, asyncio.TimeoutError):
            raise HTTPException(404, 'Public profile photo unavailable.', headers={'Cache-Control': 'no-store'})
        finally:
            if task.done() and _image_inflight.get(url) is task:
                _image_inflight.pop(url, None)
        _images[url] = (time.monotonic() + min(TTL, 3600), image)
        while len(_images) > 64:
            _images.popitem(last=False)
    return Response(image, media_type='image/png', headers={
        'Cache-Control': 'public, max-age=3600', 'X-Content-Type-Options': 'nosniff',
        'Access-Control-Allow-Origin': '*', 'Content-Disposition': 'inline',
        'X-Avatar-Cache': 'HIT' if cache_hit else 'MISS',
    })