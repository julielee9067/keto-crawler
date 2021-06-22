import logging
import re
from typing import Any, Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import BaseUrls, WebsiteNames
from databases.db import BaseRecipeDB
from utils import get_response_content_list

logging.root.setLevel(logging.INFO)


class KetoPeopleBaseScraper(BaseRecipeDB):
    @staticmethod
    def get_url_list():
        index_url = urljoin(
            BaseUrls.KETO_PEOPLE.value, "recipe_guide?category=d4QxEKxg1D"
        )
        response = requests.get(index_url)
        soup = BeautifulSoup(response.content, "html.parser")
        return [
            urljoin(BaseUrls.KETO_PEOPLE.value, link["href"])
            for link in soup.select("div.card > span > a")
        ]

    def run(self):
        url_list = self.get_url_list()
        self.update_db(
            website_name=WebsiteNames.KETO_PEOPLE.value,
            recipe_info_dict={
                "api_crawling_id_list": [],
                "web_crawling_url_list": url_list,
            },
        )


class KetoPeopleScraper:
    def __init__(self, url_list: List[str]):
        self.url_list = url_list

    @staticmethod
    def get_recipe_name(soup: BeautifulSoup) -> str:
        return soup.select_one("p.view_tit").text.replace("레시피", "").strip()

    def get_keto_recipe_info(self, soup: BeautifulSoup, url: str) -> Dict:
        url_id = BaseRecipeDB().get_url_id_by_url_and_website_name(
            url=url, website_name=WebsiteNames.KETO_PEOPLE.value
        )
        recipe_info = {
            "recipe_name": self.get_recipe_name(soup=soup),
            "url_id": url_id,
            "yield": None,
            "yield_unit": None,
            "image_url": soup.select_one("img.fr-dii")["src"],
            "prep_time": None,
            "active_time": None,
            "total_time": None,
        }

        return recipe_info

    def get_keto_recipe_ingredients(self, soup: BeautifulSoup) -> List[Dict]:
        current_tag = soup.find(text="Ingredient")
        recipe_name = self.get_recipe_name(soup=soup)
        html = ""

        while 1:
            current_tag = current_tag.find_next("p")
            if "Recipe" in current_tag.text:
                break
            html += str(current_tag)

        soup = BeautifulSoup(html, features="lxml")
        ingredient_list = list()

        for ingredients in soup.select("span"):
            ingredient_list.extend(re.split(",\s|\s:\s", ingredients.text)[1:])

        return [
            {
                "ingredient_name": ingredient.strip(),
                "unit": None,
                "amount": None,
                "recipe_name": recipe_name,
            }
            for ingredient in ingredient_list
        ]

    def get_keto_recipe_instructions(self, soup: BeautifulSoup) -> List[Dict]:
        current_tag = soup.find(text="Recipe")
        recipe_name = self.get_recipe_name(soup=soup)
        html = ""

        while 1:
            current_tag = current_tag.find_next("p")
            if current_tag.select("br"):
                break
            html += str(current_tag)

        soup = BeautifulSoup(html, features="lxml")

        return [
            {
                "kor_description": re.sub("\d+\.\s+", "", description.text.strip()),
                "order_number": index,
                "recipe_name": recipe_name,
            }
            for index, description in enumerate(soup.select("p"))
        ]

    def get_keto_recipe_tips(self, soup: BeautifulSoup) -> Any:
        recipe_name = self.get_recipe_name(soup=soup)
        board_soup = soup.select_one("div.margin-top-xxl")
        current_tag = board_soup.find(text="TIP")
        html = ""
        while current_tag is not None:
            current_tag = current_tag.find_next("p")
            if not board_soup.find(text=current_tag.text):
                break
            html += str(current_tag)

        selected_soup = BeautifulSoup(html, features="lxml")

        return (
            [
                {
                    "tip": description.text.strip(),
                    "order_number": index,
                    "recipe_name": recipe_name,
                }
                for index, description in enumerate(selected_soup.select("p"))
                if description.text.strip()
            ]
            if selected_soup.select("p")
            else None
        )

    def run(self):
        total_recipe_info_list = list()
        response_content_list = get_response_content_list(url_list=self.url_list)

        for index, item in enumerate(response_content_list):
            soup = BeautifulSoup(item["response_content"], "html.parser")
            recipe_dict = {
                "keto_recipe_info": self.get_keto_recipe_info(
                    soup=soup, url=item["url"]
                ),
                "keto_recipe_ingredients": self.get_keto_recipe_ingredients(soup=soup),
                "keto_recipe_instructions": self.get_keto_recipe_instructions(
                    soup=soup
                ),
                "keto_recipe_tips": self.get_keto_recipe_tips(soup=soup),
            }
            total_recipe_info_list.append(recipe_dict)
            logging.info(
                f"{index + 1}/{len(response_content_list)}: Successfully scraped: {item['url']}"
            )

        return total_recipe_info_list


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = KetoPeopleBaseScraper()

    # Run when url and id list needs to be updated
    # base_scraper.run()

    url_list = base_scraper.get_new_web_url_list(
        website_name=WebsiteNames.KETO_PEOPLE.value
    )
    web_scraper = KetoPeopleScraper(url_list=url_list)
    web_recipe_dict_list = web_scraper.run()

    return web_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
