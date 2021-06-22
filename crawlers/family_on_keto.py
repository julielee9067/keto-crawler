import logging
import re
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import EMOJI_PATTERN, BaseUrls, WebsiteNames
from crawlers.cralwer import APIScraper, WebScraperWithMP
from databases.db import BaseRecipeDB
from utils import get_time_in_seconds

logging.root.setLevel(logging.INFO)


class FamilyOnKetoBaseScraper(BaseRecipeDB):
    @staticmethod
    def get_recipe_month_urls() -> List[str]:
        first_page_url = urljoin(
            BaseUrls.FAMILY_ON_KETO.value, "family-on-keto-recipes"
        )
        response = requests.get(first_page_url)
        soup = BeautifulSoup(response.content, "html.parser")

        return [link["href"] for link in soup.select("div#archives-2 > ul > li > a")]

    @staticmethod
    def get_post_id_list(month_url: str, child_conn: Connection) -> None:
        response = requests.get(month_url)
        soup = BeautifulSoup(response.content, "html.parser")
        post_urls = [link["href"] for link in soup.select("div.post-header > h2 > a")]
        post_id_list = list()
        api_url_list = list()
        for url in post_urls:
            try:
                response = requests.get(url)
                soup = BeautifulSoup(response.content, "html.parser")
                post_id = re.search(
                    r"\d+", soup.select_one("section.mv-create-card")["id"]
                )[0]
                post_id_list.append(post_id)
                api_url_list.append(url)
            except Exception:
                pass

        child_conn.send(
            {
                "api_crawling_id_list": post_id_list,
                "web_crawling_url_list": [
                    url for url in post_urls if url not in api_url_list
                ],
            }
        )
        child_conn.close()

    def divide_crawling_list(self, month_url_list: List[str]) -> Dict:
        recipe_info = list()
        processes = list()

        for url in month_url_list:
            parent_conn, child_conn = Pipe()
            recipe_info.append(parent_conn)
            process = Process(
                target=self.get_post_id_list,
                args=(url, child_conn),
            )
            processes.append(process)

        for process in processes:
            process.start()

        total_post_id_list = list()
        total_url_list = list()
        for recipe_info in recipe_info:
            recipe_info_dict = recipe_info.recv()
            total_post_id_list.extend(recipe_info_dict["api_crawling_id_list"])
            total_url_list.extend(recipe_info_dict["web_crawling_url_list"])

        for process in processes:
            process.join()

        return {
            "api_crawling_id_list": total_post_id_list,
            "web_crawling_url_list": total_url_list,
        }

    def run(self) -> None:
        month_urls = self.get_recipe_month_urls()
        recipe_info_dict = self.divide_crawling_list(month_url_list=month_urls)
        self.update_db(
            recipe_info_dict=recipe_info_dict,
            website_name=WebsiteNames.FAMILY_ON_KETO.value,
        )


class FamilyOnKetoAPIScraper(APIScraper):
    def __init__(self, api_crawling_id_list: List[str]):
        super().__init__(
            base_url=BaseUrls.FAMILY_ON_KETO.value,
            api_id_list=api_crawling_id_list,
            website_name=WebsiteNames.FAMILY_ON_KETO.value,
        )


class FamilyOnKetoWebScraper(BaseRecipeDB):
    def __init__(self, web_crawling_url_list: List[str]):
        super().__init__()
        self.url_list = web_crawling_url_list

    def get_keto_recipe_info(self, soup: BeautifulSoup, url: str) -> Dict:
        recipe_name = EMOJI_PATTERN.sub(
            r"", soup.select_one("div.post-header > h1").text
        ).strip()
        yield_raw_values = soup.select_one("span.servings")
        yield_values = (
            re.split(r"\s+(?=\d)|(?<=\d)\s+", yield_raw_values.text)
            if yield_raw_values is not None
            else [None]
        )
        time_raw_values = [
            meta.text
            for meta in soup.select("div.recipe-meta > span")
            if meta.select("i.fa-clock-o")
        ]

        active_time = None
        if time_raw_values:
            active_time = get_time_in_seconds(time_raw_values[0].split(": ")[1])

        return {
            "recipe_name": recipe_name,
            "url_id": self.get_url_id_by_url_and_website_name(
                url=url, website_name=WebsiteNames.FAMILY_ON_KETO.value
            ),
            "yield": yield_values[0],
            "yield_unit": yield_values[1] if len(yield_values) == 2 else "servings",
            "image_url": soup.select_one("div.post-img > img").get("src"),
            "prep_time": None,
            "active_time": active_time,
            "total_time": active_time,
        }

    @staticmethod
    def get_keto_recipe_ingredients(
        soup: BeautifulSoup, recipe_name: str
    ) -> List[Dict]:
        return [
            {
                "ingredient_name": ingredient.text.lower(),
                "unit": None,
                "amount": None,
                "recipe_name": recipe_name,
            }
            for ingredient in soup.select("div.recipe-ingredients > ul > li > span")
            if "ingredient" not in ingredient.text.lower()
        ]

    @staticmethod
    def get_keto_recipe_instructions(
        soup: BeautifulSoup, recipe_name: str
    ) -> List[Dict]:
        instructions = [
            {
                "eng_description": description.text.strip(),
                "order_number": index,
                "recipe_name": recipe_name,
            }
            for index, description in enumerate(soup.select("div.step-content > p"))
        ]
        if not instructions:
            raise ValueError("keto recipe doesn't exist")
        return instructions

    def run(self) -> List:
        total_recipe_info_list = list()
        url_response_list = WebScraperWithMP().get_response_list_with_mp(
            web_url_list=self.url_list
        )
        for url, content in url_response_list:
            try:
                soup = BeautifulSoup(content, "html.parser")
                keto_recipe_info = self.get_keto_recipe_info(soup=soup, url=url)
                recipe_name = keto_recipe_info["recipe_name"]
                recipe_info = {
                    "keto_recipe_info": keto_recipe_info,
                    "keto_recipe_ingredients": self.get_keto_recipe_ingredients(
                        soup=soup, recipe_name=recipe_name
                    ),
                    "keto_recipe_instructions": self.get_keto_recipe_instructions(
                        soup=soup, recipe_name=recipe_name
                    ),
                }
                total_recipe_info_list.append(recipe_info)
                logging.info(f"Family on Keto: Successfully scraped {url}")
            except Exception as e:
                logging.error(f"{url}: {e}")
                pass

        return total_recipe_info_list


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = FamilyOnKetoBaseScraper()

    # Run when lists need to be updated
    base_scraper.run()

    web_url_list = base_scraper.get_web_url_list(
        website_name=WebsiteNames.FAMILY_ON_KETO.value
    )
    api_id_list = base_scraper.get_api_id_list(
        website_name=WebsiteNames.FAMILY_ON_KETO.value
    )

    web_scraper = FamilyOnKetoWebScraper(web_crawling_url_list=web_url_list)
    api_scraper = FamilyOnKetoAPIScraper(api_crawling_id_list=api_id_list)

    api_recipe_dict_list = api_scraper.run_with_mp()
    web_recipe_dict_list = web_scraper.run()

    return api_recipe_dict_list + web_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
