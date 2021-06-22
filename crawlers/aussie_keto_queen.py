import logging
import re
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import BaseUrls, WebsiteNames
from databases.db import BaseRecipeDB
from utils import get_response_content_list

logging.root.setLevel(logging.INFO)


class AussieKetoQueenBaseScraper(BaseRecipeDB):
    @staticmethod
    def get_url_list() -> List[str]:
        index_url = urljoin(
            BaseUrls.AUSSIE_KETO_QUEEN.value, "recipes/keto-recipes-index"
        )
        response = requests.get(index_url)
        soup = BeautifulSoup(response.content, "html.parser")
        return list(set([link["href"] for link in soup.select("ul#ri-ul > li > a")]))

    def run(self):
        url_list = self.get_url_list()
        logging.info(f"Aussie Keto Queen: Found {len(url_list)} URLs")
        self.update_db(
            website_name=WebsiteNames.AUSSIE_KETO_QUEEN.value,
            recipe_info_dict={
                "api_crawling_id_list": [],
                "web_crawling_url_list": url_list,
            },
        )


class AussieKetoQueenScraper:
    def __init__(self, url_list: List[str]):
        self.url_list = url_list

    def get_keto_recipe_info(self, soup: BeautifulSoup, url: str) -> Dict:
        recipe_name = soup.select_one("h1.article-heading")
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
        yield_num = soup.select_one("span.wprm-recipe-servings")
        recipe_dict = {
            "recipe_name": recipe_name,
            "url_id": BaseRecipeDB().get_url_id_by_url_and_website_name(
                url=url, website_name=WebsiteNames.AUSSIE_KETO_QUEEN.value
            ),
            "yield": yield_num.text if yield_num is not None else None,
            "yield_unit": None,
            "image_url": soup.select_one("img.article-featured-img").get("src"),
            "prep_time": prep_time,
            "active_time": active_time,
            "total_time": prep_time + active_time,
        }
        return recipe_dict

    @staticmethod
    def get_keto_recipe_ingredients(
        soup: BeautifulSoup, recipe_name: str
    ) -> List[Dict]:
        ingredients_list = [
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
        if ingredients_list:
            return ingredients_list
        logging.error("NOT A RECIPE")
        raise Exception

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

    def get_recipe_dict_from_soup(self, soup: BeautifulSoup, url: str) -> Dict:
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
        return recipe_info

    def run(self) -> List[Dict]:
        total_recipe_info_list = list()
        response_content_list = get_response_content_list(url_list=self.url_list)
        for item in response_content_list:
            try:
                soup = BeautifulSoup(item["response_content"], "html.parser")
                recipe_info = self.get_recipe_dict_from_soup(soup=soup, url=item["url"])
                total_recipe_info_list.append(recipe_info)
                logging.info(f"Aussie Keto Queen: Successfully scraped: {item['url']}")
            except Exception as e:
                logging.error(e)
                pass

        return total_recipe_info_list


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = AussieKetoQueenBaseScraper()

    # Run when url and id list needs to be updated
    # base_scraper.run()

    url_list = base_scraper.get_web_url_list(
        website_name=WebsiteNames.AUSSIE_KETO_QUEEN.value
    )
    web_scraper = AussieKetoQueenScraper(url_list=url_list)
    web_recipe_dict_list = web_scraper.run()

    return web_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
