import logging
from logging.handlers import RotatingFileHandler

from config import CONFIG
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from chatgpt import format_conversation, check_token_price_this_month, send, \
    num_tokens_from_messages
from extract_logs import user_stats, rank_stats
from utils import user_data_to_ascii_table
from expiringdict import ExpiringDict
from usage_logging import UssageLogging

## Slack Bolt
bolt_app = AsyncApp(token=CONFIG['BOT_TOKEN'])

## Slack Request Message
WATING_MESSAGE = "잠시만 기다려주세요... :hourglass_flowing_sand:"
INITIAL_MESSAGES = [{"role": "assistant", "content": "안녕하세요! 지피티선생님입니다. 무엇이든 물어보세요. :smile:"}]
SYSTEM_MESSAGE = [{"role": "system", "content": "You are a helpful PHD professor talking to your students"}]

logger = logging.getLogger(__name__)
file_handler = RotatingFileHandler('logs/error.log',
                                   maxBytes=1024 * 1024 * 100,
                                   backupCount=20,
                                   encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
file_handler.setLevel(logging.ERROR)
logger.addHandler(file_handler)

## Flask-Caching
cache = ExpiringDict(max_len=10000, max_age_seconds=300)


@bolt_app.event("app_home_opened")
async def update_home_tab(client, event, ack):
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
        await client.views_publish(
            user_id=user_id,
            view={
                "type": "home",
                "blocks": blocks
            }
        )
        await ack()

    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.command("/대화시작")
async def start_conversation(body, ack, say):
    try:
        if body["channel_id"].startswith("D"):
            await ack(":no_entry_sign: 해당 명령어는 채널에서만 사용 가능합니다.")
        else:
            await say("안녕하세요! 지피티선생님입니다. 무엇이든 물어보세요. :smile:")
            cache[f'channel_{body["channel_id"]}'] = {"messages": INITIAL_MESSAGES, "is_pending": False}
            await ack()
    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.command("/대화끝")
async def end_conversation(body, ack, say):
    try:
        if body["channel_id"].startswith("D"):
            await ack(":no_entry_sign: 해당 명령어는 채널에서만 사용 가능합니다.")
        else:
            await say("감사합니다. 대화를 종료합니다! :wave:")
            del cache[f'channel_{body["channel_id"]}']
            await ack()
    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.command("/대화초기화")
async def reset_conversation(body, ack, say):
    try:
        if body["channel_id"].startswith("D"):
            await ack(":no_entry_sign: 해당 명령어는 채널에서만 사용 가능합니다.")
        else:
            await say("대화를 처음부터 다시 시작합니다! 무엇이든 물어보세요. :smile:")
            cache[f'channel_{body["channel_id"]}'] = {"messages": INITIAL_MESSAGES, "is_pending": False}
            await ack()
    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.command("/사용량")
async def show_usage(body, ack, say, client):
    try:
        await ack()
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

        await client.chat_postMessage(
            channel=body["channel_id"],
            blocks=blocks,
            text="test"
        )
    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.event("message")
async def handle_message(event, say, ack, client):
    channel_type = event["channel_type"]
    user_id = event["user"]
    if channel_type in ["im", "mpim"]:
        # 개인 메시지
        user_context = cache.get(f'user_{user_id}')

        if not user_context:
            cache[f'user_{user_id}'] = {"messages": INITIAL_MESSAGES, "is_pending": False}
            user_context = cache.get(f'user_{user_id}')

        if user_context and user_context["is_pending"]:
            await say(WATING_MESSAGE)
            cache[f'user_{user_id}'] = {"messages": user_context["messages"], "is_pending": True}
        else:
            try:
                with UssageLogging(user_id) as usage:
                    cache[f'user_{user_id}'] = {"messages": user_context["messages"], "is_pending": True}
                    conversations = user_context["messages"]
                    conversations.append(format_conversation(event["text"]))
                    prompt_tokens = num_tokens_from_messages(SYSTEM_MESSAGE + conversations)
                    report = []
                    bot_m = await client.chat_postMessage(
                        channel=event["channel"],
                        text=":hourglass_flowing_sand:"
                    )
                    send_cnt = 0
                    result = ""
                    for chunk in send(
                            messages=SYSTEM_MESSAGE + conversations,
                            stream=True
                    ):
                        content = chunk["choices"][0].get("delta", {}).get("content")
                        is_finish = chunk["choices"][0].get("finish_reason", None)
                        result = "".join(report).strip()
                        if content is not None:
                            send_cnt += 1
                            report.append(content)
                            if send_cnt % 2 == 0:
                                await client.chat_update(
                                    channel=event["channel"],
                                    ts=bot_m["ts"],
                                    text=result
                                )
                        if is_finish is not None:
                            await client.chat_update(
                                channel=event["channel"],
                                ts=bot_m["ts"],
                                text=result
                            )
                    completion_tokens = num_tokens_from_messages(result)
                    conversations.append(format_conversation(result, "assistant"))
                    while len(conversations) < 6:
                        del conversations[0]
                    cache[f'user_{user_id}'] = {"messages": conversations, "is_pending": False}
                    usage.tokens = completion_tokens + prompt_tokens
            except Exception as e:
                await say("대화 중 알 수 없는 오류가 발생했습니다. :cry:")
                logger.error(f"Error handling message: {e}")
    elif channel_type in ["channel", "group"]:
        # 단체 메시지
        channel_context = cache.get(f'channel_{event["channel"]}')

        if not channel_context:
            pass
        elif channel_context["is_pending"]:
            await say(WATING_MESSAGE)
            cache[f'channel_{event["channel"]}'] = {"messages": channel_context["messages"], "is_pending": True}
        else:
            try:
                with UssageLogging(user_id) as usage:
                    cache[f'channel_{event["channel"]}'] = {"messages": channel_context["messages"], "is_pending": True}
                    conversations = channel_context["messages"]
                    conversations.append(format_conversation(event["text"]))
                    prompt_tokens = num_tokens_from_messages(SYSTEM_MESSAGE + conversations)
                    report = []
                    bot_m = await client.chat_postMessage(
                        channel=event["channel"],
                        text=":hourglass_flowing_sand:"
                    )
                    send_cnt = 0
                    result = ""
                    for chunk in send(
                            messages=SYSTEM_MESSAGE + conversations,
                            stream=True
                    ):
                        content = chunk["choices"][0].get("delta", {}).get("content")
                        is_finish = chunk["choices"][0].get("finish_reason", None)
                        result = "".join(report).strip()
                        if content is not None:
                            send_cnt += 1
                            report.append(content)
                            if send_cnt % 2 == 0:
                                await client.chat_update(
                                    channel=event["channel"],
                                    ts=bot_m["ts"],
                                    text=result
                                )
                        if is_finish is not None:
                            await client.chat_update(
                                channel=event["channel"],
                                ts=bot_m["ts"],
                                text=result
                            )
                    completion_tokens = num_tokens_from_messages(result)
                    conversations.append(format_conversation(result, "assistant"))
                    while len(conversations) < 6:
                        del conversations[0]
                    cache[f'user_{user_id}'] = {"messages": conversations, "is_pending": False}
                    usage.tokens = completion_tokens + prompt_tokens
            except Exception as e:
                await say("대화 중 알 수 없는 오류가 발생했습니다. :cry:")
                logger.error(f"Error handling message: {e}")
    await ack()


async def main():
    handler = AsyncSocketModeHandler(bolt_app, CONFIG["APP_TOKEN"])
    await handler.start_async()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
