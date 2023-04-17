import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request
from flask_caching import Cache
from config import CONFIG
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from chatgpt import send_conversation_list, format_conversation, check_token_price_this_month
from extract_logs import user_stats, rank_stats
from utils import get_users, user_data_to_ascii_table

logging.basicConfig(level=logging.INFO)

## Slack Bolt
bolt_app = App(token=CONFIG['BOT_TOKEN'], signing_secret=CONFIG['SIGNING_SECRET'])

## Slack Request Message
WATING_MESSAGE = "잠시만 기다려주세요... :hourglass_flowing_sand:"
INITIAL_MESSAGES = [{"role": "assistant", "content": "안녕하세요! 지피티선생님입니다. 무엇이든 물어보세요. :smile:"}]

handler = SlackRequestHandler(bolt_app)

## Flask
app = Flask(__name__)
app.config['LOGGING_LEVEL'] = logging.ERROR
app.config['LOGGING_FORMAT'] = '%(asctime)s %(levelname)s: %(message)s'
app.config['LOGGING_LOCATION'] = 'logs/'
app.config['LOGGING_FILENAME'] = 'error.log'

if not app.debug:
    file_handler = RotatingFileHandler(app.config['LOGGING_LOCATION'] + app.config['LOGGING_FILENAME'],
                                       maxBytes=1024 * 1024 * 100,
                                       backupCount=20,
                                       encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(app.config['LOGGING_FORMAT']))
    file_handler.setLevel(app.config['LOGGING_LEVEL'])
    app.logger.addHandler(file_handler)

## Flask-Caching
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})


@bolt_app.event("app_home_opened")
def update_home_tab(client, event):
    try:
        user_id = event["user"]
        # App Home 화면 구성

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"안녕하세요 <@{user_id}>님! 사용 가능한 명령어 목록입니다 :smile:"
                },
                "accessory": {
                    "type": "image",
                    "image_url": "https://pbs.twimg.com/profile_images/625633822235693056/lNGUneLX_400x400.jpg",
                    "alt_text": "cute cat"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": """ `/대화시작` :  대화를 시작합니다. (_채널에서 사용가능_) \n\n `/대화끝` :  대화를 종료합니다. (_채널에서 사용가능_) \n\n `/대화초기화` :  대화를 처음부터 다시 시작합니다. (_채널에서 사용가능_) """
                }
            },
            {
                "type": "divider"
            }
        ]
        user_date_list, user_total_token, user_total_process_time = user_stats(user_id)
        user_table = user_data_to_ascii_table(user_date_list)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"• 이번 달 : 예상 `{user_total_token * 0.0000027}$` (`{user_total_token}토큰`), `{round(user_total_process_time, 2)}초`"
                }
            }
        )

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{user_table}```"
                }
            }
        )

        # App Home 화면 전송
        client.views_publish(
            user_id=user_id,
            view={
                "type": "home",
                "blocks": blocks
            }
        )

    except Exception as e:
        app.logger.error(f"Error handling message: {e}")


@bolt_app.command("/대화시작")
def start_conversation(body, ack, say):
    try:
        if body["channel_id"].startswith("D"):
            ack(":no_entry_sign: 해당 명령어는 채널에서만 사용 가능합니다.")
        else:
            say("안녕하세요! 지피티선생님입니다. 무엇이든 물어보세요. :smile:")
            cache.set(f'channel_{body["channel_id"]}', {"messages": INITIAL_MESSAGES, "is_pending": False})
            ack()
    except Exception as e:
        app.logger.error(f"Error handling message: {e}")


@bolt_app.command("/대화끝")
def end_conversation(body, ack, say):
    try:
        if body["channel_id"].startswith("D"):
            ack(":no_entry_sign: 해당 명령어는 채널에서만 사용 가능합니다.")
        else:
            say("감사합니다. 대화를 종료합니다! :wave:")
            cache.delete(f'channel_{body["channel_id"]}')
            ack()
    except Exception as e:
        app.logger.error(f"Error handling message: {e}")


@bolt_app.command("/대화초기화")
def reset_conversation(body, ack, say):
    try:
        if body["channel_id"].startswith("D"):
            ack(":no_entry_sign: 해당 명령어는 채널에서만 사용 가능합니다.")
        else:
            say("대화를 처음부터 다시 시작합니다! 무엇이든 물어보세요. :smile:")
            cache.set(f'channel_{body["channel_id"]}', {"messages": INITIAL_MESSAGES, "is_pending": False})
            ack()
    except Exception as e:
        app.logger.error(f"Error handling message: {e}")


@bolt_app.command("/사용량")
def show_usage(body, ack, say, client):
    try:
        ack()
        user_stat_list = rank_stats()
        total_stats = check_token_price_this_month()

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*이번달 총 사용량입니다.*"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "emoji": True,
                        "text": f"요금 - {total_stats[1]}$ (토큰 :{total_stats[0]}개)"
                    }
                ]
            },
        ]
        number_to_word = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

        for i, user_stat in enumerate(user_stat_list):
            try:
                word = number_to_word[i]
            except IndexError:
                word = "keycap_star"
            blocks += [
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":{word}: *<@{user_stat['user_id']}>님 사용량*\n"
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "plain_text",
                            "emoji": True,
                            "text": f"요금 - {round(user_stat['total_token'] * 0.0000027, 4)}$ (토큰 : {user_stat['total_token']}개), 사용 시간 - {user_stat['total_process_time']}초"
                        }
                    ]
                }
            ]

        client.chat_postMessage(
            channel=body["channel_id"],
            blocks=blocks
        )
    except Exception as e:
        app.logger.error(f"Error handling message: {e}")


@bolt_app.event("message")
def handle_message(event, say, ack, client):
    channel_type = event["channel_type"]
    user_id = event["user"]
    if channel_type in ["im", "mpim"]:
        # 개인 메시지
        user_context = cache.get(f'user_{user_id}')

        if not user_context:
            cache.set(f'user_{user_id}', {"messages": INITIAL_MESSAGES, "is_pending": False})
            user_context = cache.get(f'user_{user_id}')

        if user_context and user_context["is_pending"]:
            say(WATING_MESSAGE)
            cache.set(f'user_{user_id}', {"messages": user_context["messages"], "is_pending": True})
        else:
            try:
                cache.set(f'user_{user_id}', {"messages": user_context["messages"], "is_pending": True})
                existing_conversations = user_context["messages"]
                existing_conversations.append(format_conversation(event["text"]))
                answer, conversations = send_conversation_list(user_id, existing_conversations)
                say(answer)
                cache.set(f'user_{user_id}', {"messages": conversations, "is_pending": False})
            except Exception as e:
                say("대화 중 알 수 없는 오류가 발생했습니다. :cry:")
                app.logger.error(f"Error handling message: {e}")
    elif channel_type in ["channel", "group"]:
        # 단체 메시지
        channel_context = cache.get(f'channel_{event["channel"]}')

        if not channel_context:
            pass
        elif channel_context["is_pending"]:
            say(WATING_MESSAGE)
            cache.set(f'channel_{event["channel"]}', {"messages": channel_context["messages"], "is_pending": True})
        else:
            try:
                cache.set(f'channel_{event["channel"]}', {"messages": channel_context["messages"], "is_pending": True})
                existing_conversations = channel_context["messages"]
                existing_conversations.append(format_conversation(event["text"]))
                answer, conversations = send_conversation_list(user_id, existing_conversations)
                say(answer)
                cache.set(f'channel_{event["channel"]}', {"messages": conversations, "is_pending": False})
            except Exception as e:
                say("대화 중 알 수 없는 오류가 발생했습니다. :cry:")
                app.logger.error(f"Error handling message: {e}")
    ack()


@bolt_app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    user = body.get('user_id')
    if not user:
        user = body.get('event', {}).get('user')
    if user not in get_users():
        return None

    return next()


@app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
