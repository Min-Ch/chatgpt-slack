import openai
import requests
import time
from utils import current_month_range
from decorator import logging_decorator
from config import CONFIG

# 발급받은 OpenAI API Key 기입
API_KEY = CONFIG.get("API_KEY")

openai.api_key = API_KEY


def format_conversation(content, role='user'):
    return {
        "role": role,
        "content": content
    }


@logging_decorator
def send_conversation_list(conversations):
    tokens = 0
    response = send(conversations)
    tokens += response['usage']['total_tokens']
    answer = response["choices"][0]["message"]["content"]
    time.sleep(3)
    summarize_response = summarize(answer)
    tokens += summarize_response['usage']['total_tokens']
    summarize_answer = summarize_response["choices"][0]["message"]["content"]
    conversations.append({"role": "assistant", "content": summarize_answer})
    while len(conversations) > 4:  # 최대 5개의 대화를 유지
        del conversations[0]
    return answer, conversations, tokens


def check_token_price_this_month():
    days_of_month = current_month_range()
    url = 'https://api.openai.com/v1/usage'
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    total_tokens = 0
    for date in days_of_month:
        params = {
            'date': date,
        }
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            result = response.json()
            # 사용량 조회 결과 처리
            for data in result['data']:
                total_tokens += data.get('n_context_tokens_total', 0)
                total_tokens += data.get('n_generated_tokens_total', 0)
        else:
            print(response.json())
    # model: gpt-3.5-turbo 기준 pricing
    return total_tokens, (total_tokens * 0.0000027)


def summarize(text):
    messages = [{
        'role': 'user',
        'content': f'이 내용 한국어로 한 문장으로 요약해줘 ###\n{text}\n###'
    }]
    result = send(messages)
    return result


def send(messages, model="gpt-3.5-turbo", max_tokens=500, temperature=1):
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    return openai.ChatCompletion.create(**data)