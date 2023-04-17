import os
from dotenv import load_dotenv

load_dotenv(verbose=True)

CONFIG = {
    "BOT_TOKEN": os.getenv('BOT_TOKEN'),
    "SIGNING_SECRET": os.getenv('SIGNING_SECRET'),
    "API_KEY": os.getenv('API_KEY'),
}

USERS = ['U04HPTHH1NU']