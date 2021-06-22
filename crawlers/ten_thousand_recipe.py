import logging
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import BaseUrls, WebsiteNames
from databases.db import BaseRecipeDB
from utils import (
    get_letters_from_string,
    get_numbers_from_string,
    get_response_content_list,
    get_time_in_seconds,
)

logging.root.setLevel(logging.INFO)


class TenThousandRecipeBaseScraper(BaseRecipeDB):
    @staticmethod
    def get_pagination_urls() -> List[str]:
        index_url = urljoin(BaseUrls.TEN_THOUSAND_RECIPE.value, "recipe/list.html?q=키토")
        response = requests.get(index_url)
        soup = BeautifulSoup(response.content, "html.parser")
        pagination_elements = [
            int(get_numbers_from_string(item.text)[0])
            for item in soup.select("ul.pagination > li")
        ]
        max_num = max(pagination_elements)

        return [
            urljoin(
                BaseUrls.TEN_THOUSAND_RECIPE.value,
                f"recipe/list.html?q=키토&order=reco&page={index+1}",
            )
            for index in range(max_num)
        ]

    def get_url_list(self, pagination_url: str) -> List[str]:
        response = requests.get(pagination_url)
        soup = BeautifulSoup(response.content, "html.parser")

        return [
            urljoin(BaseUrls.TEN_THOUSAND_RECIPE.value, link["href"])
            for link in soup.select("div.common_sp_thumb > a")
        ]

    def run(self) -> None:
        url_list = list()
        pagination_urls = self.get_pagination_urls()
        for url in pagination_urls:
            url_list.extend(self.get_url_list(pagination_url=url))

        self.update_db(
            website_name=WebsiteNames.TEN_THOUSAND_RECIPE.value,
            recipe_info_dict={
                "api_crawling_id_list": [],
                "web_crawling_url_list": url_list,
            },
        )


class TenThousandRecipeScraper:
    def __init__(self, url_list: List[str]):
        self.url_list = url_list

    @staticmethod
    def get_recipe_name(soup: BeautifulSoup) -> str:
        return soup.select_one("div.view2_summary > h3").text.strip()

    def get_keto_recipe_info(self, soup: BeautifulSoup, url: str) -> Dict:
        url_id = BaseRecipeDB().get_url_id_by_url_and_website_name(
            url=url, website_name=WebsiteNames.TEN_THOUSAND_RECIPE.value
        )
        yield_val = (
            soup.select_one("span.view2_summary_info1").text
            if soup.select("span.view2_summary_info1")
            else None
        )
        active_time = (
            get_time_in_seconds(soup.select_one("span.view2_summary_info2").text)
            if soup.select("span.view2_summary_info2")
            else None
        )
        recipe_info = {
            "recipe_name": self.get_recipe_name(soup=soup),
            "url_id": url_id,
            "yield": get_numbers_from_string(yield_val)[0],
            "yield_unit": get_letters_from_string(yield_val)[0],
            "image_url": soup.select_one("img#main_thumbs")["src"],
            "prep_time": None,
            "active_time": active_time,
            "total_time": active_time,
        }

        return recipe_info

    def get_keto_recipe_ingredients(self, soup: BeautifulSoup) -> List[Dict]:
        ingredient_list = soup.select("div#divConfirmedMaterialArea > ul > a > li")
        total_ingredient_list = list()
        recipe_name = self.get_recipe_name(soup=soup)
        for ingredient in ingredient_list:
            if ingredient.select_one("span.ingre_unit").text:
                value = ingredient.select_one("span.ingre_unit").text
                amount = (
                    get_numbers_from_string(value)[0]
                    if get_numbers_from_string(value)
                    else None
                )
                unit = (
                    get_letters_from_string(value)[0]
                    if get_letters_from_string(value)
                    else None
                )
                info_dict = {
                    "ingredient_name": ingredient.text.replace(value, "").strip(),
                    "unit": unit,
                    "amount": amount,
                    "recipe_name": recipe_name,
                }
            else:
                info_dict = {
                    "ingredient_name": ingredient.text.strip(),
                    "unit": None,
                    "amount": None,
                    "recipe_name": recipe_name,
                }
            total_ingredient_list.append(info_dict)
        if not total_ingredient_list:
            for ingredient_group in soup.select("div.cont_ingre > dl > dd"):
                info_dict_list = [
                    {
                        "ingredient_name": ingredient.strip(),
                        "unit": None,
                        "amount": None,
                        "recipe_name": recipe_name,
                    }
                    for ingredient in ingredient_group.text.split(", ")
                ]
                total_ingredient_list.extend(info_dict_list)

        return total_ingredient_list

    def get_keto_recipe_instructions(self, soup: BeautifulSoup) -> List[Dict]:
        return [
            {
                "kor_description": description.text.strip(),
                "order_number": index,
                "recipe_name": self.get_recipe_name(soup=soup),
            }
            for index, description in enumerate(soup.select("div.view_step_cont"))
        ]

    def run(self) -> List[Dict]:
        total_recipe_info_list = list()
        response_content_list = get_response_content_list(url_list=self.url_list)
        for index, item in enumerate(response_content_list):
            soup = BeautifulSoup(item["response_content"], "html.parser")
            ingredients_list = self.get_keto_recipe_ingredients(soup=soup)
            instructions_list = self.get_keto_recipe_instructions(soup=soup)

            if not ingredients_list or not instructions_list:
                logging.info(f" NOT A RECIPE: {item['url']}")
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
    base_scraper = TenThousandRecipeBaseScraper()

    # Run when url and id list needs to be updated
    # base_scraper.run()

    url_list = base_scraper.get_new_web_url_list(
        website_name=WebsiteNames.TEN_THOUSAND_RECIPE.value
    )

    web_scraper = TenThousandRecipeScraper(url_list=url_list)
    web_recipe_dict_list = web_scraper.run()

    return web_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
