import re
import glob
from utils import current_year_month, current_month_range


def log_files():
    files = ["logs/usage.log"]
    files += glob.glob(f"logs/usage.log.{current_year_month()}*")
    return files


def parse_log_content(log_content):
    id, token, process_time = log_content.split('/')
    return {"id": id, "tokens": int(token), "process_time": round(float(process_time), 2)}


def stats_for_this_month():
    pattern = r"(\d{4}-\d{2}-\d{2})\s\d{2}:\d{2}:\d{2},\d{3}\s\w+:\s(.+)"
    files = log_files()
    logs = []
    user_ids = set()
    for file in files:
        try:
            with open(file, "r") as f:
                lines = [line.strip() for line in f.readlines()]
                for line in lines:
                    match = re.search(pattern, line)
                    if not match:
                        continue
                    timestamp, log_content = match.groups()
                    log_content = parse_log_content(log_content)
                    user_ids.add(log_content['id'])
                    logs.append({"timestamp": timestamp, **log_content})
        except Exception as e:
            print(e)
            pass

    result = []
    total_tokens = 0
    total_process_time = 0

    for user_id in user_ids:
        date_result = []
        for date in current_month_range():
            date_obj = {
                "date": date,
                "tokens": 0,
                "process_time": 0,
            }
            for log in logs:
                if log['timestamp'] == date and log['id'] == user_id:
                    date_obj['tokens'] += log['tokens']
                    date_obj['process_time'] += log['process_time']
                    total_tokens += log['tokens']
                    total_process_time += log['process_time']
            date_obj['process_time'] = round(date_obj['process_time'], 2)
            date_result.append(date_obj)
        user_obj = {
            "user_id": user_id,
            "date": date_result,
        }
        result.append(user_obj)
    return result


def user_stats(user_id):
    result = stats_for_this_month()
    filtered_list = list(filter(lambda x: x['user_id'] == user_id, result))
    if not filtered_list:
        raise Exception("User not found")

    user_date_list = filtered_list[0]['date']
    user_total_token = sum([x['tokens'] for x in user_date_list])
    user_total_process_time = sum([x['process_time'] for x in user_date_list])
    return user_date_list, user_total_token, user_total_process_time


def rank_stats():
    result = stats_for_this_month()
    new_list = [{
        "user_id": x['user_id'],
        "total_token": sum([y['tokens'] for y in x['date']]),
        "total_process_time": sum([y['process_time'] for y in x['date']]),
    } for x in result]
    new_list.sort(key=lambda x: x['total_token'], reverse=True)
    return new_list