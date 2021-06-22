import json
from typing import List

import requests

from config import NUTRITION_INFO_API_KEY
from constants import NUTRITION_API_PAGE_SIZE, TOTAL_NUTRITION_COUNT


def parse_nutrition_api() -> List:
    total_list = list()

    for count in range(int(TOTAL_NUTRITION_COUNT / NUTRITION_API_PAGE_SIZE) + 1):
        url = (
            f"https://koreanfood.rda.go.kr/kfi/openapi/service?"
            f"apiKey={NUTRITION_INFO_API_KEY}&pageSize={NUTRITION_API_PAGE_SIZE}&nowPage={count+1}&serviceType=AA002"
        )
        response = requests.get(url)
        obj = json.loads(response.text)
        total_list.extend((item for item in obj["service"]["list"]))

    return total_list
