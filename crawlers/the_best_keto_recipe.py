import logging
import re
import time
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from constants import BaseUrls, WebsiteNames
from crawlers.cralwer import APIScraper
from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)


class TheBestKetoRecipeBaseScraper(BaseRecipeDB):
    @staticmethod
    def get_tag_list() -> List[str]:
        url = urljoin(BaseUrls.THE_BEST_KETO_RECIPE.value, "recipe-index")
        page = requests.get(url)
        soup = BeautifulSoup(page.content, "html.parser")
        tag_list = soup.select("div.tagindex > ul > li > a")
        return [tag.text.strip().replace(" ", "-") for tag in tag_list]

    def get_recipe_id_list(self, tag_list: List[str]) -> List[str]:
        recipe_id_list = list()
        processes = list()

        for tag in tag_list:
            parent_conn, child_conn = Pipe()
            recipe_id_list.append(parent_conn)
            process = Process(
                target=self.get_recipe_id_list_by_tag, args=(tag, child_conn)
            )
            processes.append(process)

        for process in processes:
            process.start()

        total_recipe_id_list = list()
        for recipe_id in recipe_id_list:
            total_recipe_id_list.extend(recipe_id.recv())

        for process in processes:
            process.join()

        return total_recipe_id_list

    @staticmethod
    def get_recipe_id_list_by_tag(tag: str, child_conn: Connection) -> None:
        recipe_id_list = list()
        try:
            url = urljoin(BaseUrls.THE_BEST_KETO_RECIPE.value, f"tag/{tag}")
            page = requests.get(url)
            time.sleep(1)
            soup = BeautifulSoup(page.content, "html.parser")
            recipe_urls = [
                recipe["href"].strip() for recipe in soup.select("a.entry-title-link")
            ]
            logging.info(
                f"The Best Keto Recipe: Found {len(recipe_urls)} urls for tag: {tag}"
            )
            for url in recipe_urls:
                try:
                    page = requests.get(url)
                    time.sleep(1)
                    soup = BeautifulSoup(
                        markup=page.content, features="html.parser"
                    ).select_one("a.mv-create-jtr")["href"]
                    recipe_id_list.append(re.search(r"\d+", soup)[0])
                    logging.info(f"Found post id from {url}")
                except TypeError:
                    pass
        except Exception as e:
            logging.error(e)
        finally:
            child_conn.send(recipe_id_list)
            child_conn.close()

    def update_url_db(self):
        tag_list = self.get_tag_list()
        recipe_ids = self.get_recipe_id_list(tag_list=tag_list)
        BaseRecipeDB().update_db(
            website_name=WebsiteNames.THE_BEST_KETO_RECIPE.value,
            recipe_info_dict={
                "web_crawling_url_list": [],
                "api_crawling_id_list": recipe_ids,
            },
        )

    def run(self) -> None:
        # Use when need to update url list
        self.update_url_db()


class TheBestKetoRecipeScraper(APIScraper):
    def __init__(self, api_id_list: List[str]):
        super().__init__(
            base_url=BaseUrls.THE_BEST_KETO_RECIPE.value,
            api_id_list=api_id_list,
            website_name=WebsiteNames.THE_BEST_KETO_RECIPE.value,
        )


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = TheBestKetoRecipeBaseScraper()

    # Run when lists need to be updated
    # base_scraper.run()

    api_id_list = base_scraper.get_api_id_list(
        website_name=WebsiteNames.THE_BEST_KETO_RECIPE.value
    )
    api_scraper = TheBestKetoRecipeScraper(api_id_list=api_id_list)
    api_recipe_dict_list = api_scraper.run_with_mp()

    return api_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
