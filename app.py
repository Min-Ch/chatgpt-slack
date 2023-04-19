import logging

from logging.handlers import RotatingFileHandler
from config import CONFIG, WATING_MESSAGE, INITIAL_MESSAGE, SYSTEM_MESSAGE
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from open_ai import format_conversation, check_token_price_this_month, send, num_tokens_from_messages, create_image, \
    translate_to_eng
from extract_logs import user_stats, rank_stats
from utils import user_data_to_ascii_table
from context import LoggingManager
from cache import RedisManager

## Slack Bolt
bolt_app = App(token=CONFIG['BOT_TOKEN'])

logger = logging.getLogger(__name__)
file_handler = RotatingFileHandler('logs/error.log',
                                   maxBytes=1024 * 1024 * 100,
                                   backupCount=20,
                                   encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
file_handler.setLevel(logging.ERROR)
logger.addHandler(file_handler)

redis_manager = RedisManager(host=CONFIG['REDIS']['HOST'], port=CONFIG['REDIS']['PORT'], db=CONFIG['REDIS']['DB'])


@bolt_app.event("app_home_opened")
def update_home_tab(client, event, ack):
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
        ack()

    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.command("/대화시작")
def start_conversation(body, ack, say):
    try:
        if body["channel_id"].startswith("D"):
            ack(":no_entry_sign: 해당 명령어는 채널에서만 사용 가능합니다.")
        else:
            say("안녕하세요! 지피티선생님입니다. 무엇이든 물어보세요. :smile:")
            redis_manager.set(prefix="channel", key=body['channel_id'],
                              value={"messages": [INITIAL_MESSAGE]})
            redis_manager.set(prefix="channel", key=f"{body['channel_id']}_waiting", value=False)
            ack()
    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.command("/대화끝")
def end_conversation(body, ack, say):
    try:
        if body["channel_id"].startswith("D"):
            ack(":no_entry_sign: 해당 명령어는 채널에서만 사용 가능합니다.")
        else:
            say("감사합니다. 대화를 종료합니다! :wave:")
            redis_manager.delete(prefix="channel", key=body['channel_id'])
            redis_manager.delete(prefix="channel", key=f"{body['channel_id']}_waiting")
            ack()
    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.command("/대화초기화")
def reset_conversation(body, ack, say):
    try:
        if body["channel_id"].startswith("D"):
            ack(":no_entry_sign: 해당 명령어는 채널에서만 사용 가능합니다.")
        else:
            say("대화를 처음부터 다시 시작합니다! 무엇이든 물어보세요. :smile:")
            redis_manager.set(prefix="channel", key=body['channel_id'],
                              value={"messages": [INITIAL_MESSAGE]})
            redis_manager.set(prefix="channel", key=f"{body['channel_id']}_waiting", value=False)
        ack()
    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.command("/사용량")
def show_usage(body, ack, client):
    try:
        ack()
        client.views_open(
            trigger_id=body["trigger_id"],
            # A simple view payload for a modal
            view={
                "type": "modal",
                "close": {
                    "type": "plain_text",
                    "text": "닫기",
                },
                "title": {
                    "type": "plain_text",
                    "text": "사용량 확인",
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*안녕하세요 <@{body['user_id']}>님!* 원하시는 메뉴를 골라주세요"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":dollar: *전체 사용량*\n이번 달 총 사용량을 확인합니다"
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "선택",
                                "emoji": True
                            },
                            "style": "primary",
                            "action_id": "total_usage"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":bar_chart: *사용량 순위*\n전체 유저의 사용량 순위를 확인합니다"
                        },
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "선택",
                                "emoji": True
                            },
                            "style": "primary",
                            "action_id": "rank_usage"
                        }
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.command("/그림그리기")
def draw_image(body, ack, client):
    try:
        ack()
        client.views_open(
            trigger_id=body["trigger_id"],
            # A simple view payload for a modal
            view={
                "type": "modal",
                "callback_id": "draw_image",
                "title": {
                    "type": "plain_text",
                    "text": "달리 선생님의 미술 교실"
                },
                "submit": {
                    "type": "plain_text",
                    "text": "그리기"
                },
                "close": {
                    "type": "plain_text",
                    "text": "닫기"
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*안녕하세요 <@{body['user_id']}>님!* 원하시는 그림이 있으신가요?"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "input",
                        "block_id": "input_check",
                        "label": {
                            "type": "plain_text",
                            "text": "원하시는 기능을 선택해주세요:sparkles:",
                            "emoji": True
                        },
                        "element": {
                            "type": "checkboxes",
                            "options": [
                                {
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": "*번역 기능*"
                                    },
                                    "description": {
                                        "type": "mrkdwn",
                                        "text": "한글로 작성하신 경우 체크해주세요\n(체크 시 토큰이 추가적으로 사용됩니다.)"
                                    },
                                }
                            ],
                            "action_id": "is_translate",
                        },
                        "optional": True
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "input",
                        "block_id": "input_text",
                        "label": {
                            "type": "plain_text",
                            "text": "원하시는 그림에 대해서 설명해주세요:pray:",
                            "emoji": True
                        },
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "image_description",
                            "multiline": True
                        }
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.view("draw_image")
def draw_image(ack, body, client, view):
    user_id = body["user"]["id"]
    try:
        with LoggingManager(user_id=user_id) as usage:
            ack()
            is_translate = view["state"]["values"]["input_check"]["is_translate"]["selected_options"]
            image_description = view["state"]["values"]["input_text"]["image_description"]['value']
            client.chat_postMessage(channel=user_id, text="그림을 그리는 중입니다... 잠시만 기다려주세요")
            if is_translate:
                translate_description, translate_tokens = translate_to_eng(image_description)
                usage.tokens += translate_tokens
            else:
                translate_description = image_description
            response = create_image(translate_description)
            image_url = response['data'][0]['url']
            client.chat_postMessage(channel=user_id,
                                    text="그림이 완성되었습니다! :tada:",
                                    blocks=[
                                        {
                                            "type": "section",
                                            "text": {
                                                "type": "mrkdwn",
                                                "text": f"*{translate_description}*"
                                            }
                                        },
                                        {
                                            "type": "image",
                                            "title": {
                                                "type": "plain_text",
                                                "text": "그림",
                                                "emoji": True
                                            },
                                            "image_url": image_url,
                                            "alt_text": "marg"
                                        }
                                    ])
            usage.tokens += 9
    except Exception as e:
        client.chat_postMessage(channel=user_id, text=str(e))
        logger.error(f"Error handling message: {e}")


@bolt_app.action("total_usage")
def show_total_usage(ack, body, client):
    try:
        ack()
        response = client.views_update(
            view_id=body["view"]["id"],
            hash=body["view"]["hash"],
            view={
                "type": "modal",
                "title": {
                    "type": "plain_text",
                    "text": "잠시만 기다려주세요",
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": WATING_MESSAGE
                        }
                    }
                ]
            }
        )

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
        client.views_update(
            view_id=response["view"]["id"],
            hash=response["view"]["hash"],
            view={
                "type": "modal",
                "close": {
                    "type": "plain_text",
                    "text": "닫기",
                },
                "title": {
                    "type": "plain_text",
                    "text": "전체 사용량 확인",
                },
                "blocks": blocks
            }
        )
    except Exception as e:
        logger.error(f"Error handling message: {e}")


@bolt_app.action("rank_usage")
def show_rank_usage(ack, body, client):
    ack()
    user_stat_list = rank_stats()
    number_to_word = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*이번달 사용량 순위입니다.*"
            }
        }
    ]

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

    client.views_update(
        view_id=body["view"]["id"],
        hash=body["view"]["hash"],
        view={
            "type": "modal",
            "close": {
                "type": "plain_text",
                "text": "닫기",
            },
            "title": {
                "type": "plain_text",
                "text": "사용량 순위 확인",
            },
            "blocks": blocks
        }
    )


@bolt_app.event("message")
def handle_message(event, say, ack, client):
    channel_type = event["channel_type"]
    user_id = event["user"]
    if channel_type in ["im", "mpim"]:
        # 개인 메시지
        prefix = "user"
        key = user_id
        context = redis_manager.get(prefix=prefix, key=key)
        if context is None:
            context = {"messages": [INITIAL_MESSAGE]}
            redis_manager.set(prefix=prefix, key=key, value=context)
            redis_manager.set(prefix=prefix, key=key + "_waiting", value=False)
    elif channel_type in ["channel", "group"]:
        # 채널 메시지
        prefix = "channel"
        key = event["channel"]
        context = redis_manager.get(prefix=prefix, key=key)
        if context is None:
            ack()
            return
    else:
        ack()
        return

    is_waiting = redis_manager.get(prefix=prefix, key=key + "_waiting")

    if is_waiting:
        say(WATING_MESSAGE)
    else:
        try:
            with LoggingManager(user_id) as usage:
                redis_manager.set(prefix=prefix, key=key + "_waiting", value=True)
                conversations = context["messages"]
                conversations.append(format_conversation(event["text"]))
                prompt_tokens = num_tokens_from_messages([SYSTEM_MESSAGE] + conversations)
                report = []
                bot_m = client.chat_postMessage(
                    channel=event["channel"],
                    text=":hourglass_flowing_sand:"
                )
                send_cnt = 0
                result = ""
                for chunk in send(
                        messages=[SYSTEM_MESSAGE] + conversations,
                        stream=True
                ):
                    content = chunk["choices"][0].get("delta", {}).get("content")
                    is_finish = chunk["choices"][0].get("finish_reason", None)
                    result = "".join(report).strip()
                    if content is not None:
                        send_cnt += 1
                        report.append(content)
                        if send_cnt % 2 == 0:
                            client.chat_update(
                                channel=event["channel"],
                                ts=bot_m["ts"],
                                text=result
                            )
                    if is_finish is not None:
                        client.chat_update(
                            channel=event["channel"],
                            ts=bot_m["ts"],
                            text=result
                        )
                completion_tokens = num_tokens_from_messages(result)
                conversations.append(format_conversation(result, "assistant"))
                while len(conversations) > 6:
                    del conversations[0]
                usage.tokens = completion_tokens + prompt_tokens
                redis_manager.set(prefix=prefix, key=key, value={"messages": context["messages"]})
                redis_manager.set(prefix=prefix, key=key + "_waiting", value=False)
        except Exception as e:
            say("대화 중 알 수 없는 오류가 발생했습니다. :cry:")
            logger.error(f"Error handling message: {e}")
    ack()


if __name__ == "__main__":
    SocketModeHandler(bolt_app, CONFIG["APP_TOKEN"]).start()
