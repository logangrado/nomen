import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Config:
    user1: str
    user2: str
    secret_key: str


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config(
        user1=os.environ["USER_1"],
        user2=os.environ["USER_2"],
        secret_key=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
    )
