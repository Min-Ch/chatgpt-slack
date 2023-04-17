import time
import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
timedfilehandler = TimedRotatingFileHandler(filename='logs/usage.log', when='midnight', interval=1, encoding='utf-8')
timedfilehandler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
timedfilehandler.suffix = "%Y%m%d"

logger.addHandler(timedfilehandler)


def logging_decorator(func):
    def wrapper(user_id, *args, **kwargs):
        start_time = time.time()
        a, b, tokens = func(*args, **kwargs)
        logger.info(f"{user_id}/{tokens}/{time.time() - start_time}")
        return a, b

    return wrapper
