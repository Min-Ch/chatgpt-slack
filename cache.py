import json
import redis


class RedisManager:
    def __init__(self, host, port, db):
        self.rd = redis.StrictRedis(host=host, port=port, db=db)
        self.rd.flushdb()

    def get(self, prefix, key):
        result = self.rd.get(f"{prefix}:{key}")
        if result is not None:
            if isinstance(result, bytes):
                result = result.decode('utf-8')
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                pass

        return result

    def set(self, prefix, key, value, expire=300):
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False).encode('utf-8')
        elif isinstance(value, str):
            value = value.encode('utf-8')
        elif isinstance(value, bool):
            value = int(value)
        self.rd.set(f"{prefix}:{key}", value, expire)

    def delete(self, prefix, key):
        self.rd.delete(f"{prefix}:{key}")
