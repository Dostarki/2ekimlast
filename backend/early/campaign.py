from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .settings import checked_x_url, environment_values

CAMPAIGN_ID = 'x-campaign'


class CampaignSettings(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    like_url: str = Field(min_length=1, max_length=2048)
    repost_url: str = Field(min_length=1, max_length=2048)
    reply_text: str = Field(min_length=1, max_length=4000)
    reply_url: str = Field(min_length=1, max_length=2048)
    claim_text: str = Field(min_length=1, max_length=4000)

    @field_validator('like_url', 'repost_url', 'reply_url')
    @classmethod
    def valid_url(cls, value):
        return checked_x_url(value)


class CampaignUpdate(CampaignSettings):
    revision: int = Field(ge=1)


class CampaignResponse(BaseModel):
    settings: CampaignSettings
    revision: int
    updated_at: str


async def seed_campaign(db):
    # One-time migration preserves the previously active Like/Repost/Reply targets.
    # Never read editable environment settings once a campaign exists.
    if await db.campaign_settings.find_one({'_id': CAMPAIGN_ID}, {'_id': 0, 'revision': 1}):
        return
    values = environment_values()
    settings = CampaignSettings(like_url=values['X_LIKE_LINK'], repost_url=values['X_LIKE_LINK'],
                                reply_text=values['X_COMMENT_MESSAGE'], reply_url=values['X_LIKE_LINK'],
                                claim_text=values['X_SHARE_TEXT'])
    await db.campaign_settings.update_one({'_id': CAMPAIGN_ID}, {'$setOnInsert': {
        'settings': settings.model_dump(), 'revision': 1,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }}, upsert=True)


async def get_campaign(db):
    document = await db.campaign_settings.find_one({'_id': CAMPAIGN_ID}, {'_id': 0})
    if not document:
        raise HTTPException(503, 'Kampanya ayarlarına ulaşılamıyor. Lütfen daha sonra tekrar deneyin.')
    return CampaignResponse.model_validate(document)