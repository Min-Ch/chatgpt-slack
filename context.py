import time
import logging
from logging.handlers import TimedRotatingFileHandler

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)
_timedfilehandler = TimedRotatingFileHandler(filename='logs/usage.log', when='midnight', interval=1, encoding='utf-8')
_timedfilehandler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
_timedfilehandler.suffix = "%Y%m%d"

_logger.addHandler(_timedfilehandler)


class LoggingManager:
    def __init__(self, user_id):
        self.user_id = user_id
        self.tokens = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _logger.info(f"{self.user_id}/{self.tokens}/{time.time() - self.start_time}")
