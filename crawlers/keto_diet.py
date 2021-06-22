import json
import logging
import random
import re
from fractions import Fraction
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import USER_AGENT_LIST, BaseUrls, WebsiteNames
from databases.db import BaseRecipeDB
from utils import get_pt_time_in_seconds, get_response_content_list

logging.root.setLevel(logging.INFO)

HEADERS = {
    "User-Agent": random.choice(USER_AGENT_LIST),
}


class KetoDietBaseScraper(BaseRecipeDB):
    @staticmethod
    def get_pagination_urls() -> List[str]:
        index_url = urljoin(BaseUrls.KETO_DIET.value, "Blog/category/Recipes")
        response = requests.get(index_url, headers=HEADERS)
        soup = BeautifulSoup(response.content, "html.parser")
        max_page = max([int(page.text) for page in soup.select("li.PagerLink > a")])
        return [urljoin(index_url, f"?page={num+1}") for num in range(max_page)]

    def get_url_list(self, pagination_url_list: List[str]) -> List[str]:
        url_list = list()
        processes = list()

        for pagination_url in pagination_url_list:
            parent_conn, child_conn = Pipe()
            url_list.append(parent_conn)
            process = Process(
                target=self.get_url_sublist, args=(pagination_url, child_conn)
            )
            processes.append(process)

        for process in processes:
            process.start()

        total_url_list = list()
        for url_info in url_list:
            total_url_list.extend(url_info.recv())

        for process in processes:
            process.join()

        return list(set(total_url_list))

    @staticmethod
    def get_url_sublist(pagination_url: str, child_conn: Connection) -> None:
        url_list = list()
        try:
            response = requests.get(pagination_url, headers=HEADERS)
            soup = BeautifulSoup(response.content, "html.parser")
            url_list = [
                urljoin(BaseUrls.KETO_DIET.value, link["href"])
                for link in soup.select("div.post-title > h2 > a")
            ]
        except Exception as e:
            logging.error(e)
        finally:
            child_conn.send(url_list)
            child_conn.close()

    def run(self):
        pagination_urls = self.get_pagination_urls()
        url_list = self.get_url_list(pagination_url_list=pagination_urls)
        self.update_db(
            website_name=WebsiteNames.KETO_DIET.value,
            recipe_info_dict={
                "api_crawling_id_list": [],
                "web_crawling_url_list": url_list,
            },
        )


class KetoDietScraper:
    def __init__(self, url_list: List[str]):
        self.url_list = url_list

    @staticmethod
    def get_recipe_name(soup: BeautifulSoup) -> str:
        recipe_name = soup.select_one("h1[itemprop='name']").text
        if soup.select_one("h1[itemprop='name'] > br") is not None:
            recipe_name = " - ".join(
                [name.text for name in soup.select("h1[itemprop='name'] > span")]
            )

        return recipe_name

    def get_keto_recipe_info(self, soup: BeautifulSoup, url: str) -> Dict:
        url_id = BaseRecipeDB().get_url_id_by_url_and_website_name(
            url=url, website_name=WebsiteNames.KETO_DIET.value
        )
        prep_time = (
            get_pt_time_in_seconds(
                soup.select_one("time[itemprop='prepTime']").get("datetime")
            )
            if soup.select_one("time[itemprop='prepTime']")
            else 0
        )
        active_time = (
            get_pt_time_in_seconds(
                soup.select_one("time[itemprop='cookTime']").get("datetime")
            )
            if soup.select_one("time[itemprop='cookTime']")
            else 0
        )
        yield_value = (
            soup.select_one("h2#ingredients")
            if soup.select_one("h2#ingredients")
            else soup.select_one("h3#ingredients")
        )
        yield_text = yield_value.text.split("/ ")[0]
        yield_num = (
            float(
                sum(
                    Fraction(s)
                    for s in re.search("(\d+[/\d. ]*|\d)", yield_text)[0].split()
                )
            )
            if re.search("(\d+[/\d. ]*|\d)", yield_text) is not None
            else None
        )
        recipe_info = {
            "recipe_name": self.get_recipe_name(soup=soup),
            "url_id": url_id,
            "yield": yield_num,
            "yield_unit": re.search(r"(?<=\d\s)[a-zA-Z]+", yield_text)[0]
            if re.search(r"(?<=\d\s)[a-zA-Z]+", yield_text) is not None
            else None,
            "image_url": soup.select_one("a.kdPopupButton > img")["src"],
            "prep_time": prep_time,
            "active_time": active_time,
            "total_time": prep_time + active_time,
        }
        return recipe_info

    def get_keto_recipe_ingredients(self, soup: BeautifulSoup) -> List[Dict]:
        return [
            {
                "ingredient_name": ingredient.text,
                "unit": None,
                "amount": None,
                "recipe_name": self.get_recipe_name(soup=soup),
            }
            for ingredient in soup.select("li[itemprop='recipeIngredient']")
        ]

    def get_keto_recipe_instructions(self, soup: BeautifulSoup) -> List[Dict]:
        return [
            {
                "eng_description": description.text.strip(),
                "order_number": index,
                "recipe_name": self.get_recipe_name(soup=soup),
            }
            for index, description in enumerate(
                soup.select("li[itemprop='recipeInstructions']")
            )
        ]

    def get_keto_recipe_nutrition(self, soup: BeautifulSoup) -> Dict:
        other_nutrition_dict = dict()
        for item in soup.select("span.kd-data-item"):
            other_nutrition_dict[item.select("span")[0].text] = item.select("span")[
                1
            ].text
        return {
            "energy": soup.select_one("span[itemprop='calories']").text,
            "fat": soup.select_one("span[itemprop='fatContent']").text,
            "carbohydrate": soup.select_one(
                "span[itemprop='carbohydrateContent']"
            ).text,
            "protein": soup.select_one("span[itemprop='proteinContent']").text,
            "total_dietary_fiber": soup.select_one(
                "span[itemprop='fiberContent']"
            ).text,
            "recipe_name": self.get_recipe_name(soup=soup),
            "etc": json.dumps(other_nutrition_dict, indent=4, ensure_ascii=False),
        }

    def run(self) -> List[Dict]:
        total_recipe_info_list = list()

        response_content_list = get_response_content_list(
            url_list=self.url_list, headers=HEADERS
        )
        non_recipe_urls = list()
        for index, item in enumerate(response_content_list):
            soup = BeautifulSoup(item["response_content"], "html.parser")
            ingredients_list = self.get_keto_recipe_ingredients(soup=soup)
            instructions_list = self.get_keto_recipe_instructions(soup=soup)
            if not ingredients_list or not instructions_list:
                non_recipe_urls.append(item["url"])
                logging.info(f"#{len(non_recipe_urls)}: NOT A RECIPE: {item['url']}")
                continue

            recipe_dict = {
                "keto_recipe_info": self.get_keto_recipe_info(
                    soup=soup, url=item["url"]
                ),
                "keto_recipe_ingredients": ingredients_list,
                "keto_recipe_instructions": instructions_list,
                "keto_recipe_nutrition": self.get_keto_recipe_nutrition(soup=soup),
            }
            total_recipe_info_list.append(recipe_dict)
            logging.info(
                f"{index+1}/{len(response_content_list)}: Successfully scraped: {item['url']}"
            )

        return total_recipe_info_list


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = KetoDietBaseScraper()

    # Run when url and id list needs to be updated
    # base_scraper.run()

    url_list = base_scraper.get_new_web_url_list(
        website_name=WebsiteNames.KETO_DIET.value
    )
    web_scraper = KetoDietScraper(url_list=url_list)
    web_recipe_dict_list = web_scraper.run()

    return web_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
