import logging
import re
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import BaseUrls, WebsiteNames
from databases.db import BaseRecipeDB
from utils import (
    get_numbers_from_string,
    get_response_content_list,
    get_time_in_seconds,
)

logging.root.setLevel(logging.INFO)


class CharlieFoundationBaseScraper(BaseRecipeDB):
    @staticmethod
    def get_category_urls() -> List[str]:
        index_url = urljoin(BaseUrls.CHARLIE_FOUNDATION.value, "recipes")
        response = requests.get(index_url)
        soup = BeautifulSoup(response.content, "html.parser")
        links = [
            re.search(r"/(.*?)/(.*?)/", link["on"])[0]
            for link in soup.select("div.mediasplit > div.taplink")
            if re.search(r"/(.*?)/(.*?)/", link["on"])
        ]
        return [
            urljoin(BaseUrls.CHARLIE_FOUNDATION.value, link)
            for link in links
            if "recipes" in link
        ]

    @staticmethod
    def get_pagination_urls(category_url: str) -> List[str]:
        response = requests.get(category_url)
        soup = BeautifulSoup(response.content, "html.parser")
        pagination_num = soup.select("a.page-numbers")
        max_page = (
            max([int(page.text) for page in pagination_num if page.text.strip()])
            if pagination_num
            else 1
        )
        return [
            urljoin(category_url, f"page/{page_num+1}") for page_num in range(max_page)
        ]

    @staticmethod
    def get_url_list(pagination_url: str) -> List[str]:
        response = requests.get(pagination_url)
        soup = BeautifulSoup(response.content, "html.parser")
        links = soup.select("h3.post-title > a")
        return [link["href"] for link in links]

    def run(self) -> None:
        category_urls = self.get_category_urls()
        total_pagination_urls = list()
        total_url_list = list()

        for url in category_urls:
            total_pagination_urls.extend(self.get_pagination_urls(url))

        for pagination_url in total_pagination_urls:
            total_url_list.extend(self.get_url_list(pagination_url))

        self.update_db(
            website_name=WebsiteNames.CHARLIE_FOUNDATION.value,
            recipe_info_dict={
                "api_crawling_id_list": [],
                "web_crawling_url_list": total_url_list,
            },
        )


class CharlieFoundationScraper:
    def __init__(self, url_list: List[str]):
        self.url_list = url_list

    @staticmethod
    def get_recipe_name(soup: BeautifulSoup) -> str:
        return soup.select_one("h1.entry-title").text

    def get_keto_recipe_info(self, soup: BeautifulSoup, url: str) -> Dict:
        url_id = BaseRecipeDB().get_url_id_by_url_and_website_name(
            url=url, website_name=WebsiteNames.CHARLIE_FOUNDATION.value
        )
        yield_values = (
            soup.select_one("div.nutey").text if soup.select("div.nutey") else None
        )
        yield_val = (
            get_numbers_from_string(yield_values)[0]
            if get_numbers_from_string(yield_values)
            else yield_values
        )
        yield_unit = (
            re.search(r"(?<=\d\s)[a-zA-Z]+", yield_values)[0]
            if (
                yield_values is not None
                and re.search(r"(?<=\d\s)[a-zA-Z]+", yield_values)
            )
            else None
        )
        prep_time = (
            get_time_in_seconds(soup.select_one("div.nutepr").text)
            if soup.select("div.nutepr")
            else 0
        )
        active_time = (
            get_time_in_seconds(soup.select_one("div.nutec").text)
            if soup.select("div.nutec")
            else 0
        )
        recipe_info = {
            "recipe_name": self.get_recipe_name(soup=soup),
            "url_id": url_id,
            "yield": yield_val,
            "yield_unit": yield_unit,
            "image_url": soup.select_one("div.rcimg > amp-img")["src"],
            "prep_time": prep_time,
            "active_time": active_time,
            "total_time": prep_time + active_time,
        }
        return recipe_info

    def get_keto_recipe_ingredients(self, soup: BeautifulSoup) -> List[Dict]:
        return [
            {
                "ingredient_name": ingredient.text.strip(),
                "unit": None,
                "amount": None,
                "recipe_name": self.get_recipe_name(soup=soup),
            }
            for ingredient in soup.select("div.ning")
        ]

    def get_keto_recipe_instructions(self, soup: BeautifulSoup) -> List[Dict]:
        return [
            {
                "eng_description": description.text.strip(),
                "order_number": index,
                "recipe_name": self.get_recipe_name(soup=soup),
            }
            for index, description in enumerate(soup.select("span.ndtxt"))
        ]

    def get_keto_recipe_nutrition(self, soup: BeautifulSoup) -> Dict:
        nutrition_info = soup.select("div.nutel > div.nutei")
        yield_values = (
            soup.select_one("div.nutey").text if soup.select("div.nutey") else None
        )
        yield_val = (
            get_numbers_from_string(yield_values)[0]
            if get_numbers_from_string(yield_values)
            else 1
        )
        nutrition_dict = dict()
        for nutrition in nutrition_info:
            nutrition_dict[nutrition.select_one("div.nutest").text.lower()] = float(
                get_numbers_from_string(nutrition.text)[0]
            ) / float(yield_val)
        for item in soup.select("div.nuterat"):
            if "calories" in item.select_one("b").text.lower():
                nutrition_dict["energy"] = float(
                    get_numbers_from_string(item.text)[0]
                ) / float(yield_val)

        nutrition_dict.update(
            {
                "energy": nutrition_dict.pop("energy", None),
                "fat": nutrition_dict.pop("fat", None),
                "protein": nutrition_dict.pop("protein", None),
                "recipe_name": self.get_recipe_name(soup=soup),
                "carbohydrate": nutrition_dict.pop("net carb", None),
                "total_dietary_fiber": None,
            }
        )

        return nutrition_dict

    def run(self) -> List[Dict]:
        total_recipe_info_list = list()
        response_content_list = get_response_content_list(url_list=self.url_list)
        for index, item in enumerate(response_content_list):
            soup = BeautifulSoup(item["response_content"], "html.parser")

            ingredients_list = self.get_keto_recipe_ingredients(soup=soup)
            instructions_list = self.get_keto_recipe_instructions(soup=soup)

            if not ingredients_list or not instructions_list:
                logging.info(f"NOT A RECIPE: {item['url']}")
                continue

            recipe_dict = {
                "keto_recipe_info": self.get_keto_recipe_info(
                    soup=soup, url=item["url"]
                ),
                "keto_recipe_ingredients": self.get_keto_recipe_ingredients(soup=soup),
                "keto_recipe_instructions": self.get_keto_recipe_instructions(
                    soup=soup
                ),
                "keto_recipe_nutrition": self.get_keto_recipe_nutrition(soup=soup),
            }
            total_recipe_info_list.append(recipe_dict)
            logging.info(
                f"{index+1}/{len(response_content_list)}: Successfully scraped: {item['url']}"
            )

        return total_recipe_info_list


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = CharlieFoundationBaseScraper()

    # Run when url and id list needs to be updated
    # base_scraper.run()

    url_list = base_scraper.get_new_web_url_list(
        website_name=WebsiteNames.CHARLIE_FOUNDATION.value
    )

    web_scraper = CharlieFoundationScraper(url_list=url_list)
    web_recipe_dict_list = web_scraper.run()

    return web_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
