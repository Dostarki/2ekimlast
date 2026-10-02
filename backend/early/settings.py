import os
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

from dotenv import dotenv_values
from .models import PublicConfig, TaskConfig

ENV_PATH = Path(__file__).parent / '.env'


def environment_values():
    values = {**os.environ, **dotenv_values(ENV_PATH)}
    return {**values, **{key.removeprefix('EARLY_'): value for key, value in values.items() if key.startswith('EARLY_')}}


def checked_x_url(value):
    parsed = urlparse(value)
    if (parsed.scheme != 'https' or parsed.hostname not in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}
            or parsed.username or parsed.password or parsed.port not in {None, 443}
            or any(character.isspace() or ord(character) < 32 for character in value) or '\\' in value):
        raise ValueError('Bağlantı HTTPS ile başlayan bir x.com veya twitter.com adresi olmalıdır.')
    return value


def public_config(campaign):
    # Editable links/copy come ONLY from the persisted admin campaign.
    # Environment values below are infrastructure and unchanged public labels.
    values = environment_values()
    composer = urlparse(checked_x_url(values['X_SHARE_LINK']))
    reply_url = urlunparse(composer._replace(query=urlencode({
        'text': campaign.reply_text, 'url': campaign.reply_url}), fragment=''))
    urls = {'follow': checked_x_url(values['X_FOLLOW_LINK']), 'like': campaign.like_url,
            'repost': campaign.repost_url, 'comment': reply_url}
    tasks = [TaskConfig(id=key, title=title, text=values[f'X_{key.upper()}_TEXT'], url=urls[key], action=action)
             for key, title, action in [('follow', 'UPLINK', 'Follow'), ('like', 'SIGNAL', 'Like'),
                                       ('repost', 'RELAY', 'Repost'), ('comment', 'VOICE', 'Reply')]]
    origin = values['PUBLIC_APP_URL'].rstrip('/')
    if urlparse(origin).scheme not in {'https', 'http'} or not urlparse(origin).netloc:
        raise ValueError('PUBLIC_APP_URL must be an absolute HTTP(S) URL.')
    share_url = urlunparse(composer._replace(query=urlencode({
        'text': f'{campaign.claim_text}\n\n{campaign.like_url}'}), fragment=''))
    return PublicConfig(tasks=tasks, x_profile_url=checked_x_url(values['X_PROFILE_LINK']),
                        comment_message=campaign.reply_text, share_text=campaign.claim_text,
                        share_url=share_url, public_url=origin)