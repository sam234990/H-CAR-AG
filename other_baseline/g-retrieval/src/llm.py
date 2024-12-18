import logging
from openai import OpenAI
import time


log = logging.getLogger(__name__)


def llm_invoker(
    input_text, args, temperature=0.7, max_tokens=1500, max_retries=5, json=False
):

    if "llama" in args.engine.lower():
        api_key = "ollama"
        base_url = args.api_base
    else:
        api_key = args.api_key
        base_url = args.api_base

    engine = args.engine
    client = OpenAI(api_key=api_key, base_url=base_url)
    # messages = [
    #     {
    #         "role": "system",
    #         "content": "You are an AI assistant that helps people find information.",
    #     }
    # ]
    messages = []
    message_prompt = {"role": "user", "content": input_text}
    messages.append(message_prompt)
    # 准备用于传递给 API 的参数字典
    parameters = {
        "model": engine,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    }

    # 如果 json 为 True，加入 response_format 参数
    if json:
        parameters["response_format"] = {"type": "json_object"}

    retries = 0
    success = False
    result = None
    total_token = 0

    while not success and retries < max_retries:
        try:
            response = client.chat.completions.create(**parameters)
            result = response.choices[0].message.content
            total_token += response.usage.total_tokens
            success = True
        except Exception as e:
            retries += 1
            print(f"OpenAI error, retrying... ({retries}/{max_retries})")
            time.sleep(2)

    if not success:
        print("Failed after maximum retries.")
        # 可以抛出异常或返回 None
        raise Exception("Failed to get a response from OpenAI after multiple retries.")

    return result, total_token


if __name__ == "__main__":
    test_input_text = "What is the capital of France?"
    result, total_token = llm_invoker(test_input_text)
    print(f"llm_invoker result: {result}")
    print(f"llm_invoker total_token: {total_token}")
