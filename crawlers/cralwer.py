import json
import logging
import re
import time
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from typing import Any, Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)


class WebScraperWithMP:
    def get_response_list_with_mp(self, web_url_list: List[str]) -> List:
        url_response_list = list()
        processes = list()

        for i in range(0, len(web_url_list), 10):
            url_sublist = web_url_list[i : i + 10]
            parent_conn, child_conn = Pipe()
            url_response_list.append(parent_conn)
            process = Process(
                target=self.get_response_sublist_with_mp, args=(url_sublist, child_conn)
            )
            processes.append(process)

        for process in processes:
            process.start()

        total_url_response_list = list()
        for url_response_sublist in url_response_list:
            total_url_response_list.extend(url_response_sublist.recv())

        for process in processes:
            process.join()

        return total_url_response_list

    def get_response_sublist_with_mp(
        self, url_sublist: List[str], child_conn: Connection
    ):
        url_response_sublist = list()
        for url in url_sublist:
            try:
                response = requests.get(url)
                time.sleep(1)
                url_response_sublist.append([url, response.content])
                logging.info(f"Parsed {url}")
            except Exception as e:
                logging.error(e)
                pass
        child_conn.send(url_response_sublist)
        child_conn.close()


class APIScraperWithMP:
    def get_base_recipe_dict_list_with_mp(
        self, api_id_list: List[str], base_url: str
    ) -> List[Dict]:
        recipe_info_list = list()
        processes = list()

        for i in range(0, len(api_id_list), 10):
            id_sublist = api_id_list[i : i + 10]
            parent_conn, child_conn = Pipe()
            recipe_info_list.append(parent_conn)
            process = Process(
                target=self.get_recipe_dict_with_mp,
                args=(base_url, id_sublist, child_conn),
            )
            processes.append(process)

        for process in processes:
            process.start()

        total_recipe_dict_list = list()
        for recipe_info_sublist in recipe_info_list:
            total_recipe_dict_list.extend(recipe_info_sublist.recv())

        for process in processes:
            process.join()

        return total_recipe_dict_list

    def get_recipe_dict_with_mp(
        self, base_url: str, id_sublist: List[str], child_conn: Connection
    ) -> None:
        recipe_dict_list = list()
        for post_id in id_sublist:
            try:
                recipe_dict = self.get_recipe_dict_by_post_id(
                    post_id=post_id, base_url=base_url
                )
                recipe_dict.update({"post_id": post_id})
                logging.info(f"Successfully scraped: {post_id}")
                recipe_dict_list.append(recipe_dict)
            except Exception as e:
                logging.error(e)
                pass
        child_conn.send(recipe_dict_list)
        child_conn.close()

    @staticmethod
    def get_recipe_dict_by_post_id(base_url: str, post_id: Any) -> Dict:
        url = urljoin(base_url, f"/wp-json/mv-create/v1/creations/{post_id}")
        response = requests.get(url)
        time.sleep(1)

        return json.loads(response.text)


class APIScraper(BaseRecipeDB):
    def __init__(
        self,
        api_id_list: List[Any],
        base_url: str,
        website_name: str,
        time_sleep: int = 0,
        headers: Dict = None,
    ):
        super().__init__()
        self.time_sleep = time_sleep
        self.headers = headers
        self.base_url = base_url
        self.api_id_list = api_id_list
        self.website_name = website_name

    def get_recipe_dict_by_post_id(self, post_id: Any) -> Dict:
        url = urljoin(self.base_url, f"/wp-json/mv-create/v1/creations/{post_id}")
        response = requests.get(url, headers=self.headers)
        time.sleep(1)

        return json.loads(response.text)

    def get_keto_recipe_info(self, recipe_dict: Dict, post_id: Any) -> Dict:
        yield_values = (
            re.split(r"\s+(?=\d)|(?<=\d)\s+", recipe_dict.get("yield"))
            if recipe_dict.get("yield")
            else [None]
        )
        if yield_values[0] is None and recipe_dict.get("nutrition") is not None:
            yield_values = [
                re.search(r"\d+", recipe_dict["nutrition"].get("number_of_servings"))[0]
            ]

        return {
            "recipe_name": recipe_dict.get("title"),
            "url_id": self.get_url_id_by_post_id_and_website_name(
                post_id=post_id, website_name=self.website_name
            ),
            "yield": yield_values[0],
            "yield_unit": yield_values[1] if len(yield_values) == 2 else None,
            "image_url": recipe_dict.get("thumbnail_uri"),
            "prep_time": recipe_dict.get("prep_time"),
            "active_time": recipe_dict.get("active_time"),
            "total_time": recipe_dict.get("total_time"),
        }

    @staticmethod
    def get_keto_recipe_ingredients(recipe_dict: Dict, recipe_name: str) -> List[Dict]:
        return [
            {
                "ingredient_name": ingredient.get("original_text").strip(),
                "unit": None,
                "amount": None,
                "recipe_name": recipe_name,
            }
            for ingredient in recipe_dict["supplies"]
        ]

    @staticmethod
    def get_keto_recipe_instructions(recipe_dict: Dict, recipe_name: str) -> List[Dict]:
        soup = BeautifulSoup(recipe_dict["instructions"], "html.parser")
        return [
            {
                "order_number": index,
                "eng_description": instruction.strip(),
                "recipe_name": recipe_name,
            }
            for index, instruction in enumerate(re.split(r"\.|\d+\.", soup.get_text()))
            if instruction.strip()
        ]

    @staticmethod
    def get_keto_recipe_nutrition(
        recipe_dict: Dict, yield_num: str, recipe_name: str
    ) -> Dict:
        try:
            nutrition_dict = (
                recipe_dict["nutrition"] if recipe_dict["nutrition"] else dict()
            )
            updated_dict = {
                k: nutrition_dict[k] for k in nutrition_dict if nutrition_dict[k]
            }
            db_nutrition_dict = {
                "energy": updated_dict.get("calories"),
                "fat": updated_dict.get("total_fat"),
                "carbohydrate": updated_dict.get("net_carbs"),
                "protein": updated_dict.get("protein"),
                "total_dietary_fiber": updated_dict.get("fiber"),
            }
            db_nutrition_dict.update(
                (key, f"{float(value) * int(yield_num):.2f}")
                for key, value in db_nutrition_dict.items()
                if value and yield_num
            )
            db_nutrition_dict["recipe_name"] = recipe_name

            return db_nutrition_dict
        except Exception as e:
            logging.error(e)

    def get_keto_recipe_total_info(
        self, recipe_dict: Dict, post_id: str = None
    ) -> Dict:
        recipe_post_id = post_id if post_id is not None else recipe_dict["post_id"]
        keto_recipe_info = self.get_keto_recipe_info(
            recipe_dict=recipe_dict, post_id=recipe_post_id
        )
        recipe_name = keto_recipe_info["recipe_name"]
        yield_num = keto_recipe_info["yield"]

        recipe_info = {
            "keto_recipe_info": keto_recipe_info,
            "keto_recipe_ingredients": self.get_keto_recipe_ingredients(
                recipe_dict=recipe_dict, recipe_name=recipe_name
            ),
            "keto_recipe_instructions": self.get_keto_recipe_instructions(
                recipe_dict=recipe_dict, recipe_name=recipe_name
            ),
            "keto_recipe_nutrition": self.get_keto_recipe_nutrition(
                recipe_dict=recipe_dict,
                yield_num=yield_num,
                recipe_name=recipe_name,
            ),
        }
        logging.info(f"Successfully scraped: {recipe_post_id}")
        return recipe_info

    def run_with_mp(self) -> List[Dict]:
        total_recipe_info_list = list()
        recipe_dict_list = APIScraperWithMP().get_base_recipe_dict_list_with_mp(
            base_url=self.base_url, api_id_list=self.api_id_list
        )
        for recipe_dict in recipe_dict_list:
            recipe_info = self.get_keto_recipe_total_info(recipe_dict=recipe_dict)
            total_recipe_info_list.append(recipe_info)

        return total_recipe_info_list

    def run(self) -> List[Dict]:
        total_recipe_info_list = list()
        for post_id in self.api_id_list:
            recipe_dict = self.get_recipe_dict_by_post_id(post_id=post_id)
            recipe_info = self.get_keto_recipe_total_info(
                recipe_dict=recipe_dict, post_id=post_id
            )
            total_recipe_info_list.append(recipe_info)

        return total_recipe_info_list
