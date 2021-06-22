import json
import logging
import re
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
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


class LowCarbMavenBaseScraper(BaseRecipeDB):
    @staticmethod
    def get_category_urls() -> List[str]:
        index_url = urljoin(
            BaseUrls.LOW_CARB_MAVEN.value, "low-carb-keto-recipe-index/"
        )
        response = requests.get(index_url)
        soup = BeautifulSoup(response.content, "html.parser")

        return [
            link["href"]
            for link in soup.select("div#wpupg-grid-by-recipe-features > a")
        ]

    def get_url_list(self, category_url_list: List[str]) -> List[str]:
        url_list = list()
        processes = list()

        for category_url in category_url_list:
            parent_conn, child_conn = Pipe()
            url_list.append(parent_conn)
            process = Process(
                target=self.get_url_sublist, args=(category_url, child_conn)
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
    def get_url_sublist(category_url: str, child_conn: Connection) -> None:
        url_sublist = list()
        try:
            response = requests.get(category_url)
            soup = BeautifulSoup(response.content, "html.parser")
            page_url_list = [
                link["href"] for link in soup.select("div.pagination > ul > li > a")
            ]
            page_num_list = re.findall(
                r"\d+", "".join(re.findall(r"/\d+/", "".join(page_url_list)))
            )
            max_page = max(page_num_list) if page_num_list else 1
            pagination_urls = [
                urljoin(category_url, f"page/{i+1}") for i in range(0, int(max_page))
            ]

            for pagination_url in pagination_urls:
                response = requests.get(pagination_url)
                soup = BeautifulSoup(response.content, "html.parser")
                url_list = [link["href"] for link in soup.select("a.entry-title-link")]
                url_sublist.extend(url_list)
                logging.info(f"Found {len(url_sublist)} urls from {category_url}")

        except Exception as e:
            logging.error(e)
        finally:
            child_conn.send(url_sublist)
            child_conn.close()

    def run(self):
        category_url_list = self.get_category_urls()
        url_list = self.get_url_list(category_url_list=category_url_list)
        self.update_db(
            website_name=WebsiteNames.LOW_CARB_MAVEN.value,
            recipe_info_dict={
                "api_crawling_id_list": [],
                "web_crawling_url_list": url_list,
            },
        )


class LowCarbMavenScraper:
    def __init__(self, url_list: List[str]):
        self.url_list = url_list

    @staticmethod
    def get_keto_recipe_info(json_obj: Dict, url: str) -> Dict:
        url_id = BaseRecipeDB().get_url_id_by_url_and_website_name(
            url=url, website_name=WebsiteNames.LOW_CARB_MAVEN.value
        )
        prep_time = get_time_in_seconds(json_obj.get("prepTime"))
        active_time = get_time_in_seconds(json_obj.get("cookTime"))
        yield_val = json_obj.get("recipeYield")
        recipe_info = {
            "recipe_name": json_obj["name"],
            "url_id": url_id,
            "yield": yield_val[0] if yield_val is not None else None,
            "yield_unit": None,
            "image_url": json_obj["image"][0],
            "prep_time": prep_time,
            "active_time": active_time,
            "total_time": prep_time + active_time,
        }
        return recipe_info

    @staticmethod
    def get_keto_recipe_ingredients(json_obj: Dict) -> List[Dict]:
        return [
            {
                "ingredient_name": ingredient,
                "unit": None,
                "amount": None,
                "recipe_name": json_obj["name"],
            }
            for ingredient in json_obj["recipeIngredient"]
        ]

    @staticmethod
    def get_keto_recipe_instructions(json_obj: Dict) -> List[Dict]:
        instruction_list = list()
        for instruction in json_obj["recipeInstructions"]:
            if instruction["@type"] == "HowToStep":
                instruction_list.append(instruction["text"])
            else:
                instruction_list.extend(
                    [item["text"] for item in instruction["itemListElement"]]
                )
        return [
            {
                "eng_description": description.strip(),
                "order_number": index,
                "recipe_name": json_obj["name"],
            }
            for index, description in enumerate(instruction_list)
        ]

    @staticmethod
    def get_keto_recipe_nutrition(json_obj: Dict) -> Dict:
        nutrition_dict = json_obj.get("nutrition")
        if nutrition_dict is not None:
            serving_size = float(
                get_numbers_from_string(nutrition_dict.get("servingSize"))[0]
            )
            nutrition = {
                "energy": get_numbers_from_string(nutrition_dict.get("calories"))[0],
                "fat": get_numbers_from_string(nutrition_dict.get("fatContent"))[0],
                "carbohydrate": get_numbers_from_string(
                    nutrition_dict.get("carbohydrateContent")
                )[0],
                "protein": get_numbers_from_string(
                    nutrition_dict.get("proteinContent")
                )[0],
                "total_dietary_fiber": get_numbers_from_string(
                    nutrition_dict.get("fiberContent")
                )[0],
            }
            nutrition.update(
                (key, float(value) * serving_size) for key, value in nutrition.items()
            )
            nutrition["recipe_name"] = json_obj["name"]

            return nutrition

    def run(self) -> List[Dict]:
        total_recipe_info_list = list()
        response_content_list = get_response_content_list(url_list=self.url_list)
        for item in response_content_list:
            try:
                soup = BeautifulSoup(item["response_content"], "html.parser")
                json_obj = json.loads(
                    soup.select_one(
                        "script.yoast-schema-graph[type='application/ld+json']"
                    ).contents[0]
                )

                recipe_dict = next(
                    item for item in json_obj["@graph"] if item["@type"] == "Recipe"
                )
                recipe_info = {
                    "keto_recipe_info": self.get_keto_recipe_info(
                        json_obj=recipe_dict, url=item["url"]
                    ),
                    "keto_recipe_ingredients": self.get_keto_recipe_ingredients(
                        json_obj=recipe_dict
                    ),
                    "keto_recipe_instructions": self.get_keto_recipe_instructions(
                        json_obj=recipe_dict
                    ),
                    "keto_recipe_nutrition": self.get_keto_recipe_nutrition(
                        json_obj=recipe_dict
                    ),
                }
                total_recipe_info_list.append(recipe_info)
                logging.info(f"Low Carb Maven: Successfully scraped: {item['url']}")
            except Exception as e:
                logging.error(f"{item['url']}: {e}")
                pass

        return total_recipe_info_list


def get_total_recipe_dict_list() -> List[Dict]:
    base_scraper = LowCarbMavenBaseScraper()

    # Run when url and id list needs to be updated
    # base_scraper.run()

    url_list = base_scraper.get_new_web_url_list(
        website_name=WebsiteNames.LOW_CARB_MAVEN.value
    )

    web_scraper = LowCarbMavenScraper(url_list=url_list)
    web_recipe_dict_list = web_scraper.run()

    return web_recipe_dict_list


if __name__ == "__main__":
    get_total_recipe_dict_list()
