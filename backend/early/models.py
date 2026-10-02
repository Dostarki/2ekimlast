import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

TASK_IDS = {'follow', 'like', 'repost', 'comment'}


class TaskConfig(BaseModel):
    id: str
    title: str
    text: str
    url: str
    action: str


class PublicConfig(BaseModel):
    tasks: list[TaskConfig]
    x_profile_url: str
    comment_message: str
    share_text: str
    share_url: str
    public_url: str
    verification: Literal['self_declared'] = 'self_declared'


class ParticipationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    handle: str = Field(min_length=1, max_length=16)
    wallet: str = Field(min_length=42, max_length=42)
    completed_tasks: list[str] = Field(min_length=4, max_length=4)
    consent: Literal[True]
    referred_by: str | None = Field(default=None, max_length=10)

    @field_validator('handle')
    @classmethod
    def valid_handle(cls, value):
        value = value.strip().lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9_]{1,15}', value):
            raise ValueError('Use 1–15 letters, numbers or underscores for your X handle.')
        return value

    @field_validator('wallet')
    @classmethod
    def valid_wallet(cls, value):
        if not re.fullmatch(r'0x[a-fA-F0-9]{40}', value):
            raise ValueError('Enter a valid EVM wallet address: 0x followed by 40 hex characters.')
        if int(value[2:], 16) == 0:
            raise ValueError('The zero address cannot receive an allocation.')
        return value

    @field_validator('completed_tasks')
    @classmethod
    def all_tasks(cls, value):
        if set(value) != TASK_IDS:
            raise ValueError('Complete all four missions before claiming early access.')
        return value

    @field_validator('referred_by')
    @classmethod
    def valid_referral(cls, value):
        if not value:
            return None
        value = value.strip().upper()
        if not re.fullmatch(r'[A-Z0-9]{8}', value):
            raise ValueError('Invalid referral code.')
        return value


class AgentPublic(BaseModel):
    handle: str
    number: int
    ref_code: str
    cell: str
    agent_class: str
    tier: str
    created_at: str
    verification: Literal['self_declared'] = 'self_declared'


class RegistryStats(BaseModel):
    count: int
    status: str = 'online'