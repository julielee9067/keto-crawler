import logging
import random
import re
import time
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import USER_AGENT_LIST, BaseUrls, WebsiteNames
from crawlers.cralwer import APIScraper
from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)

HEADERS = {
    "Host": "www.the-girl-who-ate-everything.com",
    "User-Agent": random.choice(USER_AGENT_LIST),
}


class TheGirlWhoAteEverythingBaseScraper(BaseRecipeDB):
    @staticmethod
    def get_pagination_urls() -> List[str]:
        first_page_url = urljoin(
            BaseUrls.THE_GIRL_WHO_ATE_EVERYTHING.value, "category/keto-recipes"
        )
        response = requests.get(first_page_url, headers=HEADERS)
        time.sleep(1)
        soup = BeautifulSoup(response.content, "html.parser")
        pagination_urls = [link["href"] for link in soup.select("a.page-numbers")]
        pagination_urls.append(first_page_url)

        return list(set(pagination_urls))

    @staticmethod
    def get_post_urls(paginated_url: str) -> List[str]:
        response = requests.get(paginated_url, headers=HEADERS)
        soup = BeautifulSoup(response.content, "html.parser")

        return [link["href"] for link in soup.select("div.archive-post > a")]

    @staticmethod
    def divide_crawling_list(url_list: List[str]) -> Dict:
        recipe_id_list = list()
        api_url_list = list()
        for url in url_list:
            try:
                response = requests.get(url, headers=HEADERS)
                time.sleep(1)
                soup = BeautifulSoup(response.content, "html.parser")
                recipe_id = re.search(
                    r"\d+", soup.select_one("section.mv-create-card")["id"]
                )[0]
                logging.info(f"{url}: Found {recipe_id}")
                recipe_id_list.append(recipe_id)
                api_url_list.append(url)
            except Exception:
                pass
        logging.info(
            f"The Girl Who Ate Everything: total of {len(recipe_id_list)} API urls"
        )

        return {
            "api_crawling_id_list": recipe_id_list,
            "web_crawling_url_list": [
                url for url in url_list if url not in api_url_list
            ],
        }

    def run(self) -> None:
        pagination_urls = self.get_pagination_urls()
        url_list = list()
        for pagination_url in pagination_urls:
            url_list.extend(self.get_post_urls(pagination_url))
        recipe_info_dict = self.divide_crawling_list(url_list)
        self.update_db(
            website_name=WebsiteNames.THE_GIRL_WHO_ATE_EVERYTHING.value,
            recipe_info_dict=recipe_info_dict,
        )


class TheGirlWhoAteEverythingAPIScraper(APIScraper):
    def __init__(self, api_crawling_id_list: List[str]):
        super().__init__(
            base_url=BaseUrls.THE_GIRL_WHO_ATE_EVERYTHING.value,
            headers=HEADERS,
            time_sleep=1,
            api_id_list=api_crawling_id_list,
            website_name=WebsiteNames.THE_GIRL_WHO_ATE_EVERYTHING.value,
        )


class TheGirlWhoAteEverythingWebScraper:
    def __init__(self, web_crawling_url_list: List[str]):
        self.url_list = web_crawling_url_list

    def get_keto_recipe_info(self, soup: BeautifulSoup, url: str) -> Dict:
        try:
            recipe_name = soup.select_one("h1.post-title").text
            prep_time = (
                int(soup.select("span.wprm-recipe-prep_time-minutes")[0].text) * 60
                if soup.select("span.wprm-recipe-prep_time-minutes")
                else 0
            )
            active_time = (
                int(soup.select("span.wprm-recipe-cook_time-minutes")[0].text) * 60
                if soup.select("span.wprm-recipe-cook_time-minutes")
                else 0
            )
            return {
                "recipe_name": recipe_name,
                "url_id": BaseRecipeDB().get_url_id_by_url_and_website_name(
                    url=url, website_name=WebsiteNames.THE_GIRL_WHO_ATE_EVERYTHING.value
                ),
                "yield": soup.select_one("span.wprm-recipe-servings").text,
                "yield_unit": soup.select_one("span.wprm-recipe-details-unit").text,
                "image_url": soup.find("img", {"data-pin-title": recipe_name}).get(
                    "data-jpibfi-src"
                ),
                "prep_time": prep_time,
                "active_time": active_time,
                "total_time": prep_time + active_time,
            }
        except Exception as e:
            logging.error(f"{url}: {e}")
            pass

    @staticmethod
    def get_keto_recipe_ingredients(
        soup: BeautifulSoup, recipe_name: str
    ) -> List[Dict]:
        return [
            {
                "ingredient_name": ingredient.select_one(
                    "span.wprm-recipe-ingredient-name"
                ).text.strip(),
                "unit": ingredient.select_one("span.wprm-recipe-ingredient-unit").text
                if ingredient.select("span.wprm-recipe-ingredient-unit")
                else None,
                "amount": ingredient.select_one(
                    "span.wprm-recipe-ingredient-amount"
                ).text
                if ingredient.select("span.wprm-recipe-ingredient-amount")
                else None,
                "recipe_name": recipe_name,
            }
            for ingredient in soup.select("li.wprm-recipe-ingredient")
        ]

    @staticmethod
    def get_keto_recipe_instructions(
        soup: BeautifulSoup, recipe_name: str
    ) -> List[Dict]:
        return [
            {
                "eng_description": description.text.strip(),
                "order_number": index,
                "recipe_name": recipe_name,
            }
            for index, description in enumerate(
                soup.select("div.wprm-recipe-instruction-text")
            )
            if description.text.strip()
        ]

    @staticmethod
    def get_keto_recipe_nutrition(
        soup: BeautifulSoup, yield_num: str, recipe_name: str
    ) -> Dict:
        nutrition = soup.select_one("div.wprm-recipe-nutrition-container")
        nutrition_dict = dict()
        if nutrition:
            nutrition_dict = dict(re.findall(r"(\w+): ((?:\d+)+)", nutrition.text))
            nutrition_dict.update(
                (key, f"{float(value.strip())*int(yield_num):.2f}")
                for key, value in nutrition_dict.items()
            )
        db_nutrition_dict = {
            "energy": nutrition_dict.get("Calories"),
            "fat": nutrition_dict.get("Fat"),
            "carbohydrate": nutrition_dict.get("Carbohydrates"),
            "protein": nutrition_dict.get("Protein"),
            "total_dietary_fiber": nutrition_dict.get("Fiber"),
            "recipe_name": recipe_name,
        }
        return db_nutrition_dict

    def run(self) -> List[Dict]:
        total_recipe_info_list = list()
        for url in self.url_list:
            try:
                response = requests.get(url, headers=HEADERS)
                soup = BeautifulSoup(response.content, "html.parser")
                keto_recipe_info = self.get_keto_recipe_info(soup=soup, url=url)
                yield_num = keto_recipe_info["yield"]
                recipe_name = keto_recipe_info["recipe_name"]
                recipe_info = {
                    "keto_recipe_info": keto_recipe_info,
                    "keto_recipe_ingredients": self.get_keto_recipe_ingredients(
                        soup=soup, recipe_name=recipe_name
                    ),
                    "keto_recipe_instructions": self.get_keto_recipe_instructions(
                        soup=soup, recipe_name=recipe_name
                    ),
                    "keto_recipe_nutrition": self.get_keto_recipe_nutrition(
                        soup=soup, yield_num=yield_num, recipe_name=recipe_name
                    ),
                }
                total_recipe_info_list.append(recipe_info)
                logging.info(
                    f"The Girl Who Ate Everything: Successfully scraped: {url}"
                )
            except Exception as e:
                logging.error(e)
                pass

        return total_recipe_info_list


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = TheGirlWhoAteEverythingBaseScraper()

    # Run when url and id list needs to be updated
    # base_scraper.run()

    api_crawling_id_list = base_scraper.get_api_id_list(
        website_name=WebsiteNames.THE_GIRL_WHO_ATE_EVERYTHING.value
    )
    web_crawling_url_list = base_scraper.get_web_url_list(
        website_name=WebsiteNames.THE_GIRL_WHO_ATE_EVERYTHING.value
    )

    api_scraper = TheGirlWhoAteEverythingAPIScraper(
        api_crawling_id_list=api_crawling_id_list
    )
    web_scraper = TheGirlWhoAteEverythingWebScraper(
        web_crawling_url_list=web_crawling_url_list
    )
    web_recipe_dict_list = web_scraper.run()
    api_recipe_dict_list = api_scraper.run()

    return web_recipe_dict_list + api_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
