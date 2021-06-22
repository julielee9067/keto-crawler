import logging
import re
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import Any, Dict, List
from urllib.parse import urljoin

import pandas
import requests
from bs4 import BeautifulSoup

from constants import RULED_ME_NUTRITION_COLUMN_LIST, BaseUrls, WebsiteNames
from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)


class RuledMeBaseScraper:
    @staticmethod
    def get_keto_recipe_category_urls() -> List[str]:
        url = urljoin(BaseUrls.RULED_ME.value, "keto-recipes")
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        categories = soup.select("ul.main-nav-sub > li > a")

        return [link["href"] for link in categories if "keto-recipes" in link["href"]]

    @staticmethod
    def get_paginated_urls(url: str) -> List[str]:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        pagination_nums = [
            re.findall(r"\d+", link["href"])
            for link in soup.select("div.navigation > ul > li > a")
        ]
        max_num = max([int(num[0]) for num in pagination_nums if num])

        return [urljoin(url, f"page/{num+1}") for num in range(max_num)]

    def update_keto_recipe_urls(self, category_urls: List):
        url_info_list = list()
        processes = list()

        for category_url in category_urls:
            parent_conn, child_conn = Pipe()
            url_info_list.append(parent_conn)
            process = Process(
                target=self.get_keto_recipe_url,
                args=(
                    category_url,
                    child_conn,
                ),
            )
            processes.append(process)

        for process in processes:
            process.start()

        total_url_list = list()
        for url_info in url_info_list:
            total_url_list.extend(url_info.recv())

        for process in processes:
            process.join()

        return total_url_list

    def get_keto_recipe_url(self, category_url: str, child_conn: Connection):
        try:
            url = urljoin(BaseUrls.RULED_ME.value, category_url)
            paginated_urls = self.get_paginated_urls(url=url)
            total_url_list = list()
            for paginated_url in paginated_urls:
                response = requests.get(paginated_url, timeout=10)
                soup = BeautifulSoup(response.content, "html.parser")
                recipe_list = soup.select("div.hfeed > div > a")
                logging.info(
                    f"Ruled Me: found {len(recipe_list)} recipe urls for {category_url}"
                )
                total_url_list.extend([link["href"] for link in recipe_list])
            child_conn.send(total_url_list)
        except Exception as e:
            logging.error(e)
            child_conn.send([])
        finally:
            child_conn.close()

    def update_url_db(self):
        base_scraper = RuledMeBaseScraper()
        category_urls = base_scraper.get_keto_recipe_category_urls()
        total_recipe_urls = base_scraper.update_keto_recipe_urls(
            category_urls=category_urls
        )
        BaseRecipeDB().update_db(
            website_name=WebsiteNames.RULED_ME.value,
            recipe_info_dict={
                "web_crawling_url_list": total_recipe_urls,
                "api_crawling_id_list": [],
            },
        )

    def run(self):
        self.update_url_db()


class RuledMeScraper:
    def get_instructions(self, soup: BeautifulSoup) -> List[str]:
        return [
            instruction.getText().strip()
            for instruction in soup.select("li.instruction")
        ]

    def get_ingredients(self, soup: BeautifulSoup) -> List[str]:
        ingredient_list = soup.select("div.entry-content > ul > li")
        return [ingredient.getText() for ingredient in ingredient_list]

    def get_yield(self, soup: BeautifulSoup) -> List[Any]:
        yield_select = soup.select("p#zlrecipe-yield > span")
        recipe_yield = yield_select[0].getText() if yield_select else ""
        yield_num_list = re.findall("\d+", recipe_yield)
        yield_unit_list = re.findall("[a-zA-Z]+", recipe_yield)
        yield_num = yield_num_list[0] if yield_num_list else None
        yield_unit = yield_unit_list[0] if yield_unit_list else None

        return [yield_num, yield_unit]

    def get_nutrition_values(self, soup: BeautifulSoup) -> Dict:
        try:
            data_table = soup.select("table")
            df_list = pandas.read_html(str(data_table))
            df = df_list[0]
            column_names = df[0].tolist()
            index = (
                column_names.index("Totals")
                if "Totals" in column_names
                else column_names.index("Total")
            )
            return dict(zip(RULED_ME_NUTRITION_COLUMN_LIST, df.values[index]))
        except Exception as e:
            logging.error(f"Error while getting nutrition: {e}")
            pass

    def parse_url(self, url_sublist: List[str], child_conn: Connection) -> None:
        try:
            recipe_dict_list = list()
            for url in url_sublist:
                logging.info(f"Ruled Me: parsing {url}")
                response = requests.get(url)
                soup = BeautifulSoup(response.content, "html.parser")
                recipe_name = (
                    soup.select("h1")[0].getText() if soup.select("h1") else None
                )
                image_url = (
                    soup.select("div.postImage_f > img")[0]["data-lazy-src"]
                    if soup.select("div.postImage_f > img")
                    else None
                )
                recipe_dict = {
                    "nutrition": self.get_nutrition_values(soup=soup),
                    "yield": self.get_yield(soup=soup)[0],
                    "yield_unit": self.get_yield(soup=soup)[1],
                    "ingredients": self.get_ingredients(soup=soup),
                    "instructions": self.get_instructions(soup=soup),
                    "recipe_name": recipe_name,
                    "image_url": image_url,
                    "url_id": BaseRecipeDB().get_url_id_by_url_and_website_name(
                        url=url, website_name=WebsiteNames.RULED_ME.value
                    ),
                }
                recipe_dict_list.append(recipe_dict)
            child_conn.send(recipe_dict_list)
        except Exception as e:
            logging.error(f"Error while parsing url: {e}")
            child_conn.send([])
        finally:
            child_conn.close()

    def parse_urls(self, url_list: List[str]) -> List[Dict]:
        parsed_info_list = list()
        processes = list()

        for i in range(0, len(url_list), 40):
            url_sublist = url_list[i : i + 40]
            parent_conn, child_conn = Pipe()
            parsed_info_list.append(parent_conn)
            process = Process(
                target=self.parse_url,
                args=(
                    url_sublist,
                    child_conn,
                ),
            )
            processes.append(process)

        for process in processes:
            process.start()

        total_parsed_info = [
            recipe_dict
            for parsed_info in parsed_info_list
            for recipe_dict in parsed_info.recv()
            if recipe_dict.get("recipe_name") is not None
        ]

        for process in processes:
            process.join()

        return total_parsed_info

    def run(self) -> List[Dict]:
        recipe_urls = BaseRecipeDB().get_web_url_list(
            website_name=WebsiteNames.RULED_ME.value
        )
        recipe_dict_list = self.parse_urls(url_list=recipe_urls)
        return recipe_dict_list


def get_total_recipe_dict_list() -> List[Dict]:
    # Run when lists need to be updated
    # base_scraper = RuledMeBaseScraper()
    # base_scraper.run()

    web_scraper = RuledMeScraper()
    url_recipe_dict_list = web_scraper.run()

    return url_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
