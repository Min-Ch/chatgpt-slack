import os
from dotenv import load_dotenv

load_dotenv(verbose=True)

CONFIG = {
    "BOT_TOKEN": os.getenv('BOT_TOKEN'),
    "SIGNING_SECRET": os.getenv('SIGNING_SECRET'),
    "API_KEY": os.getenv('API_KEY'),
    "APP_TOKEN": os.getenv('APP_TOKEN'),
    "REDIS": {
        "HOST": os.getenv('REDIS_HOST'),
        "PORT": os.getenv('REDIS_PORT'),
        "DB": os.getenv('REDIS_DB'),
    }
}

## Slack Request Message
WATING_MESSAGE = "잠시만 기다려주세요... :hourglass_flowing_sand:"
INITIAL_MESSAGE = {"role": "assistant", "content": "안녕하세요! 지피티선생님입니다. 무엇이든 물어보세요. :smile:"}
SYSTEM_MESSAGE = {"role": "system", "content": "You are a helpful PHD professor talking to your students"}
