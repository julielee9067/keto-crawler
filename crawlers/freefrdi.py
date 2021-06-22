import logging
import random
from typing import Any, Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import USER_AGENT_LIST, BaseUrls, WebsiteNames
from databases.db import BaseRecipeDB
from utils import get_response_content_list

logging.root.setLevel(logging.INFO)

HEADERS = {
    "User-Agent": random.choice(USER_AGENT_LIST),
}


class FreeFrdiBaseScraper(BaseRecipeDB):
    def get_pagination_urls(
        self, soup: BeautifulSoup = None, url_list: List[str] = None
    ) -> List[str]:
        if url_list is None:
            url_list = list()
            index_url = urljoin(BaseUrls.FREE_FRDI.value, "category/recipe/")
            response = requests.get(index_url, headers=HEADERS)
            soup = BeautifulSoup(response.content, "html.parser")
            url_list.append(index_url)

        if soup.select_one("div.nav-previous > a") is not None:
            prev_page_url = soup.select_one("div.nav-previous > a")["href"]
            response = requests.get(prev_page_url, headers=HEADERS)
            soup = BeautifulSoup(response.content, "html.parser")
            url_list.append(prev_page_url)
            return self.get_pagination_urls(soup=soup, url_list=url_list)

        return url_list

    def get_url_list(self, pagination_url: str) -> List[str]:
        response = requests.get(pagination_url, headers=HEADERS)
        soup = BeautifulSoup(response.content, "html.parser")
        return [link["href"] for link in soup.select("h2.entry-title > a")]

    def run(self):
        url_list = list()
        pagination_urls = self.get_pagination_urls()
        for url in pagination_urls:
            url_list.extend(self.get_url_list(pagination_url=url))

        self.update_db(
            website_name=WebsiteNames.FREE_FRDI.value,
            recipe_info_dict={
                "api_crawling_id_list": [],
                "web_crawling_url_list": url_list,
            },
        )


class FreeFrdiScraper:
    def __init__(self, url_list: List[str]):
        self.url_list = url_list

    @staticmethod
    def get_recipe_name(soup: BeautifulSoup) -> str:
        return soup.select_one("h1.entry-title").text.strip()

    def get_keto_recipe_info(self, soup: BeautifulSoup, url: str) -> Dict:
        url_id = BaseRecipeDB().get_url_id_by_url_and_website_name(
            url=url, website_name=WebsiteNames.FREE_FRDI.value
        )
        recipe_info = {
            "recipe_name": self.get_recipe_name(soup=soup),
            "url_id": url_id,
            "yield": None,
            "yield_unit": None,
            "image_url": soup.select_one("div.entry-image > img")["src"],
            "prep_time": None,
            "active_time": None,
            "total_time": None,
        }

        return recipe_info

    def get_keto_recipe_ingredients(self, soup: BeautifulSoup) -> List[Dict]:
        ingredient_tags = [
            item
            for item in soup.select("div.entry-content > h2")
            if "재료" in item.text or "소스" in item.text
        ]
        ingredient_list = [
            tag.find_next("ul").contents
            for tag in ingredient_tags
            if tag.find_next("ul")
        ]
        table_ingredient_list = [
            tag.find_next("tbody").contents
            for tag in ingredient_tags
            if tag.find_next("tbody")
        ]
        table_ingredients = (
            [
                item.get_text(strip=True, separator="|")
                for ingredient in table_ingredient_list[0]
                for item in ingredient.select("tr > td")
                if item.select("a")
            ]
            if table_ingredient_list
            else []
        )

        total_ingredient_list = list()
        for table_ingredient in table_ingredients:
            splitted_list = table_ingredient.split("|")
            for i in range(0, len(splitted_list), 2):
                total_ingredient_list.append(
                    {
                        "ingredient_name": splitted_list[i],
                        "unit": None,
                        "amount": splitted_list[i + 1],
                        "recipe_name": self.get_recipe_name(soup=soup),
                    }
                )
        total_ingredient_list.extend(
            [
                {
                    "ingredient_name": ingredient.text.strip(),
                    "unit": None,
                    "amount": None,
                    "recipe_name": self.get_recipe_name(soup=soup),
                }
                for ingredient in [
                    item for sublist in ingredient_list for item in sublist
                ]
            ]
        )

        return total_ingredient_list

    def get_keto_recipe_instructions(self, soup: BeautifulSoup) -> List[Dict]:
        try:
            tag = (
                soup.find(text="만드는 법")
                if soup.find(text="만드는 법") is not None
                else soup.find(text="만드는 방법")
            )
            tip_tag = soup.find(text="TIP")

            if tag is None:
                return list()
            elif tag.find_next("ol") and (
                tip_tag is None or tip_tag.find_all_previous("ol")
            ):
                instruction_list = [
                    {
                        "kor_description": description.text.strip(),
                        "order_number": index,
                        "recipe_name": self.get_recipe_name(soup=soup),
                    }
                    for index, description in enumerate(
                        tag.find_next("ol").select("li")
                    )
                ]
            elif tag.find_next("ul"):
                instruction_list = [
                    {
                        "kor_description": description.text.strip(),
                        "order_number": index,
                        "recipe_name": self.get_recipe_name(soup=soup),
                    }
                    for index, description in enumerate(
                        tag.find_next("ul").select("li")
                    )
                ]
            else:
                instruction_list = [
                    {
                        "kor_description": description.text.strip(),
                        "order_number": index,
                        "recipe_name": self.get_recipe_name(soup=soup),
                    }
                    for index, description in enumerate(
                        tag.parent.find_next_siblings("p")
                    )
                ]

            return instruction_list

        except Exception as e:
            logging.error(f"Instruction: {e}")

    def get_keto_recipe_tips(self, soup: BeautifulSoup) -> Any:
        tip_tag = soup.find(text="TIP")

        if tip_tag is None:
            return None

        if tip_tag.find_next("ol"):
            return [
                {
                    "tip": description.text.strip(),
                    "order_number": index,
                    "recipe_name": self.get_recipe_name(soup=soup),
                }
                for index, description in enumerate(
                    tip_tag.find_next("ol").select("li")
                )
            ]

        return None

    def run(self) -> List[Dict]:
        total_recipe_info_list = list()
        response_content_list = get_response_content_list(
            url_list=self.url_list, headers=HEADERS
        )
        error_urls = list()
        for index, item in enumerate(response_content_list):
            try:
                soup = BeautifulSoup(item["response_content"], "html.parser")
                ingredients_list = self.get_keto_recipe_ingredients(soup=soup)
                instructions_list = self.get_keto_recipe_instructions(soup=soup)
                tip_list = self.get_keto_recipe_tips(soup=soup)

                if not ingredients_list or not instructions_list:
                    logging.info(f" NOT A RECIPE: {item['url']}")
                    continue

                recipe_dict = {
                    "keto_recipe_info": self.get_keto_recipe_info(
                        soup=soup, url=item["url"]
                    ),
                    "keto_recipe_ingredients": ingredients_list,
                    "keto_recipe_instructions": instructions_list,
                    "keto_recipe_tips": tip_list,
                }
                total_recipe_info_list.append(recipe_dict)
                logging.info(
                    f"{index+1}/{len(response_content_list)}: Successfully scraped: {item['url']}"
                )
            except Exception as e:
                logging.error(e)
                error_urls.append(item["url"])
                continue

        return total_recipe_info_list


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = FreeFrdiBaseScraper()

    # Run when url and id list needs to be updated
    # base_scraper.run()

    url_list = base_scraper.get_new_web_url_list(
        website_name=WebsiteNames.FREE_FRDI.value
    )
    # url_list = ["https://freefrdi.com/imketo-coconut-tortilla/"]

    web_scraper = FreeFrdiScraper(url_list=url_list)
    web_recipe_dict_list = web_scraper.run()

    return web_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
