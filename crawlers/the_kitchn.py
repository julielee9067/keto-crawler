import json
import logging
import random
import time
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import USER_AGENT_LIST, BaseUrls, WebsiteNames
from databases.db import BaseRecipeDB
from utils import get_numbers_from_string, get_time_in_seconds

logging.root.setLevel(logging.INFO)

HEADERS = {
    "Host": "www.thekitchn.com",
    "User-Agent": random.choice(USER_AGENT_LIST),
    "referer": "https://www.thekitchn.com/recipes",
}


class TheKitchnBaseScraper(BaseRecipeDB):
    def get_category_urls(self) -> List[str]:
        index_url = urljoin(BaseUrls.THE_KITCHN.value, "/recipes/keto")
        response = requests.get(index_url, headers=HEADERS)
        time.sleep(2)
        soup = BeautifulSoup(response.content, "html.parser")

        return [
            urljoin(BaseUrls.THE_KITCHN.value, link["href"])
            for link in soup.select("a.Teaser__headline")
        ]

    def get_url_list_from_category_url(self, category_url: str) -> List[str]:
        response = requests.get(category_url, headers=HEADERS)
        time.sleep(2)
        soup = BeautifulSoup(response.content, "html.parser")
        url_list = [
            urljoin(BaseUrls.THE_KITCHN.value, link["href"])
            for link in soup.select("a.Teaser__headline")
        ]
        logging.info(f"Found {len(url_list)} urls from {category_url}")

        return url_list

    def run(self):
        category_urls = self.get_category_urls()
        url_list = list()
        logging.info(f"Found {len(category_urls)} urls from index page")

        for url in category_urls:
            url_list.extend(self.get_url_list_from_category_url(category_url=url))
        url_list = list(set(url_list))

        self.update_db(
            website_name=WebsiteNames.THE_KITCHN.value,
            recipe_info_dict={
                "api_crawling_id_list": [],
                "web_crawling_url_list": url_list,
            },
        )


class TheKitchnScraper:
    def __init__(self, url_list: List[str]):
        self.url_list = url_list

    def get_keto_recipe_info(self, json_obj: Dict, url: str) -> Dict:
        url_id = BaseRecipeDB().get_url_id_by_url_and_website_name(
            url=url, website_name=WebsiteNames.THE_KITCHN.value
        )
        prep_time = get_time_in_seconds(json_obj.get("prepTime"))
        active_time = get_time_in_seconds(json_obj.get("cookTime"))
        return {
            "recipe_name": json_obj["name"],
            "url_id": url_id,
            "yield": json_obj["recipeYield"],
            "yield_unit": None,
            "image_url": json_obj["image"][0],
            "prep_time": prep_time,
            "active_time": active_time,
            "total_time": prep_time + active_time,
        }

    def get_keto_recipe_ingredients(self, json_obj: Dict) -> List[Dict]:
        return [
            {
                "ingredient_name": ingredient,
                "unit": None,
                "amount": None,
                "recipe_name": json_obj["name"],
            }
            for ingredient in json_obj["recipeIngredient"]
        ]

    def get_keto_recipe_instructions(self, json_obj: Dict) -> List[Dict]:
        return [
            {
                "eng_description": description["text"].strip(),
                "order_number": index,
                "recipe_name": json_obj["name"],
            }
            for index, description in enumerate(json_obj["recipeInstructions"])
        ]

    def get_keto_recipe_nutrition(self, json_obj: Dict) -> Dict:
        nutrition_dict = json_obj["nutrition"]
        serving_size = int(nutrition_dict["servingSize"])
        nutrition = {
            "energy": nutrition_dict["calories"],
            "fat": get_numbers_from_string(nutrition_dict["fatContent"])[0],
            "carbohydrate": get_numbers_from_string(
                nutrition_dict["carbohydrateContent"]
            )[0],
            "protein": get_numbers_from_string(nutrition_dict["proteinContent"])[0],
        }
        nutrition.update(
            (key, float(value) * serving_size) for key, value in nutrition.items()
        )
        nutrition["recipe_name"] = json_obj["name"]
        nutrition["total_dietary_fiber"] = None

        return nutrition

    def run(self) -> List[Dict]:
        total_recipe_info_list = list()
        for index, url in enumerate(self.url_list):
            try:
                response = requests.get(url, headers=HEADERS)
                time.sleep(2)
                soup = BeautifulSoup(response.content, "html.parser")
                json_obj = json.loads(
                    soup.select_one(
                        "script.json-ld-recipe[type='application/ld+json']"
                    ).contents[0]
                )
                recipe_info = {
                    "keto_recipe_info": self.get_keto_recipe_info(
                        json_obj=json_obj, url=url
                    ),
                    "keto_recipe_ingredients": self.get_keto_recipe_ingredients(
                        json_obj=json_obj
                    ),
                    "keto_recipe_instructions": self.get_keto_recipe_instructions(
                        json_obj=json_obj
                    ),
                    "keto_recipe_nutrition": self.get_keto_recipe_nutrition(
                        json_obj=json_obj
                    ),
                }
                total_recipe_info_list.append(recipe_info)
                logging.info(
                    f"{index}/{len(self.url_list)} The Kitchn: Successfully scraped: {url}"
                )
            except Exception as e:
                logging.error(f"{url}: {e}")
                pass

        return total_recipe_info_list


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = TheKitchnBaseScraper()

    # Run when url and id list needs to be updated
    # base_scraper.run()

    url_list = base_scraper.get_web_url_list(website_name=WebsiteNames.THE_KITCHN.value)
    web_scraper = TheKitchnScraper(url_list=url_list)
    web_recipe_dict_list = web_scraper.run()

    return web_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
