import openai
import requests
import tiktoken
from utils import current_month_range
from config import CONFIG

# 발급받은 OpenAI API Key 기입
API_KEY = CONFIG.get("API_KEY")

openai.api_key = API_KEY


def format_conversation(content, role='user'):
    return {
        "role": role,
        "content": content
    }


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
            raise Exception(f"Error: {response.status_code} {response.text}")
    # model: gpt-3.5-turbo 기준 pricing
    return total_tokens, (total_tokens * 0.0000027)


def send(messages, model="gpt-3.5-turbo-0301", max_tokens=500, temperature=0.7, stream=False):
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    return openai.ChatCompletion.create(**data)


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301"):
    """Returns the number of tokens used by a list of messages."""
    if model == "gpt-3.5-turbo":
        print("Warning: gpt-3.5-turbo may change over time. Returning num tokens assuming gpt-3.5-turbo-0301.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301")
    elif model == "gpt-4":
        print("Warning: gpt-4 may change over time. Returning num tokens assuming gpt-4-0314.")
        return num_tokens_from_messages(messages, model="gpt-4-0314")
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model == "gpt-4-0314":
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")

    encoding = tiktoken.encoding_for_model(model)

    num_tokens = 0
    if type(messages) == list:
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    elif type(messages) == str:
        num_tokens += len(encoding.encode(messages))
    else:
        raise TypeError(f"messages must be a list or str, not {type(messages)}")
    return num_tokens


def translate_to_eng(text):
    content = f"아래를 영어로 번역해줘 \n {text}"
    response = send([format_conversation(content, role='user')])
    return response['choices'][0]['message']["content"], response['usage']["total_tokens"]


def create_image(prompt, n=1, size="512x512"):
    return openai.Image.create(
        prompt=prompt,
        n=n,
        size=size
    )

openai.ErrorObject