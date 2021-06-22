import logging
import random
import re
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import EXCEPTION_URLS, USER_AGENT_LIST, BaseUrls, WebsiteNames
from databases.db import BaseRecipeDB
from utils import get_response_content_list

logging.root.setLevel(logging.INFO)

HEADERS = {
    "User-Agent": random.choice(USER_AGENT_LIST),
}


class KetogenicDietResourceBaseScraper(BaseRecipeDB):
    @staticmethod
    def get_url_list():
        index_url = urljoin(
            BaseUrls.KETOGENIC_DIET_RESOURCE.value, "/low-carb-recipes.html"
        )
        response = requests.get(index_url, headers=HEADERS)
        soup = BeautifulSoup(response.content, "html.parser")
        return [
            link["href"]
            for link in soup.select("div.Liner > ul > li > a")
            if link["href"] not in EXCEPTION_URLS
        ]

    def run(self):
        url_list = self.get_url_list()
        self.update_db(
            website_name=WebsiteNames.KETOGENIC_DIET_RESOURCE.value,
            recipe_info_dict={
                "api_crawling_id_list": [],
                "web_crawling_url_list": url_list,
            },
        )


class KetogenicDietResourceScraper:
    def __init__(self, url_list: List[str]):
        self.url_list = url_list

    def get_recipe_names(self, soup: BeautifulSoup) -> List[str]:
        title_elements = (
            soup.select("div#ContentColumn div.Liner h3")
            if soup.select("div#ContentColumn div.Liner h3")
            else soup.select("div#ContentColumn div.Liner h2")
        )
        if not title_elements:
            title_elements = soup.select("div#ContentColumn div.Liner h1")
        return [item.text.strip() for item in title_elements if item.text.strip()]

    def get_keto_recipe_info(self, soup: BeautifulSoup, url: str) -> List[Dict]:
        url_id = BaseRecipeDB().get_url_id_by_url_and_website_name(
            url=url, website_name=WebsiteNames.KETOGENIC_DIET_RESOURCE.value
        )
        recipe_names = self.get_recipe_names(soup=soup)
        total_recipe_dict = [
            {
                "recipe_name": recipe_name,
                "url_id": url_id,
                "yield": None,
                "yield_unit": None,
                "image_url": soup.select_one("div.ImageBlock > img")["src"],
                "prep_time": None,
                "active_time": None,
                "total_time": None,
            }
            for recipe_name in recipe_names
        ]

        return total_recipe_dict

    def get_keto_recipe_ingredients(self, soup: BeautifulSoup) -> List[List]:
        ingredient_info = soup.select("div#ContentColumn div.Liner ul")
        recipe_names = self.get_recipe_names(soup=soup)
        total_ingredient_list = list()
        for recipe_name, ingredient_list in zip(recipe_names, ingredient_info):
            ingredient_result = list()
            for ingredient in ingredient_list.select("li"):
                try:
                    result = {
                        "ingredient_name": ingredient.text.strip(),
                        "unit": None,
                        "amount": None,
                        "recipe_name": recipe_name,
                    }
                    ingredient_result.append(result)
                except AttributeError as e:
                    logging.error(f"{recipe_name}: {e}")
                    pass
            total_ingredient_list.append(ingredient_result)

        return total_ingredient_list

    def get_keto_recipe_instructions(self, soup: BeautifulSoup) -> List[List]:
        instruction_info = soup.select("div#ContentColumn div.Liner > ol")
        recipe_names = self.get_recipe_names(soup=soup)
        total_instruction_list = list()
        for recipe_name, instruction_content in zip(recipe_names, instruction_info):
            result_list = [
                {
                    "eng_description": description.text.strip(),
                    "order_number": index,
                    "recipe_name": recipe_name,
                }
                for index, description in enumerate(instruction_content.select("li"))
            ]
            total_instruction_list.append(result_list)

        if not instruction_info:
            instruction_info = soup.select("div#ContentColumn div.Liner > p")
            for recipe_name, instruction_content in zip(recipe_names, instruction_info):
                result_list = [
                    {
                        "eng_description": description.strip(),
                        "order_number": index,
                        "recipe_name": recipe_name,
                    }
                    for index, description in enumerate(
                        instruction_content.text.split(".")
                    )
                    if description.strip()
                ]
                total_instruction_list.append(result_list)

        return total_instruction_list

    def run(self) -> List[Dict]:
        total_recipe_info_list = list()

        response_content_list = get_response_content_list(
            url_list=self.url_list, headers=HEADERS
        )
        for index, item in enumerate(response_content_list):
            soup = BeautifulSoup(item["response_content"], "html.parser")
            soup = BeautifulSoup(
                re.sub(r"<\/style(?<!>)\s+", "</style>", str(soup)), "html.parser"
            )
            ingredients_list = self.get_keto_recipe_ingredients(soup=soup)
            instructions_list = self.get_keto_recipe_instructions(soup=soup)

            if not ingredients_list or not instructions_list:
                logging.error(f"NOT A RECIPE: {item['url']}")
                continue

            recipe_dict = {
                "keto_recipe_info": self.get_keto_recipe_info(
                    soup=soup, url=item["url"]
                ),
                "keto_recipe_ingredients": ingredients_list,
                "keto_recipe_instructions": instructions_list,
            }
            total_recipe_info_list.append(recipe_dict)
            logging.info(
                f"{index+1}/{len(response_content_list)}: Successfully scraped: {item['url']}"
            )

        return total_recipe_info_list


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = KetogenicDietResourceBaseScraper()

    # Run when url and id list needs to be updated
    # base_scraper.run()

    url_list = base_scraper.get_web_url_list(
        website_name=WebsiteNames.KETOGENIC_DIET_RESOURCE.value
    )
    # url_list = ["https://www.ketogenic-diet-resource.com/low-carb-appetizers.html"]
    web_scraper = KetogenicDietResourceScraper(url_list=url_list[:1])
    web_recipe_dict_list = web_scraper.run()
    return web_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
