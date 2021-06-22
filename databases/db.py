import logging
from typing import Any, Dict, List

import pymysql

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_USERNAME
from constants import EXCEPTION_URLS


class BaseDBConnection:
    def __init__(self):
        self.db = pymysql.connect(
            user=DB_USERNAME,
            passwd=DB_PASSWORD,
            host=DB_HOST,
            db=DB_NAME,
            charset="utf8",
        )
        self.cursor = self.db.cursor(pymysql.cursors.DictCursor)


class BaseRecipeDB(BaseDBConnection):
    def get_recipe_id_by_recipe_and_website_name(
        self, recipe_name: str, website_name: str
    ) -> str:
        url_ids = tuple(self.get_web_url_id_list(website_name=website_name))
        recipe_name = recipe_name.replace("'", "\\'")
        query = f"""
                    SELECT recipe_id from keto_recipe where recipe_name='{recipe_name}' and url_id in {url_ids}
                """
        self.cursor.execute(query)
        row = self.cursor.fetchone()
        return row["recipe_id"]

    def get_web_url_id_list(self, website_name: str) -> List[str]:
        query = f"""
                    SELECT url_id from keto_recipe_urls where website_name='{website_name}'
                """
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        return [data["url_id"] for data in rows if data["url_id"] is not None]

    def delete_url_from_keto_recipe_urls(self, url: str) -> None:
        query = f"""
                    DELETE from keto_recipe_urls where url='{url}'
                """
        self.cursor.execute(query)
        self.db.commit()
        logging.info(f"{url} successfully deleted. ")

    def get_url_id_by_url_and_website_name(self, url: str, website_name: str):
        query = f"""
                    SELECT url_id from keto_recipe_urls where url='{url}' and website_name='{website_name}'
                """
        self.cursor.execute(query)
        row = self.cursor.fetchone()
        return row["url_id"]

    def get_url_id_by_post_id_and_website_name(self, post_id: Any, website_name: str):
        query = f"""
                    SELECT url_id from keto_recipe_urls where post_id='{post_id}' and website_name='{website_name}'
                """
        self.cursor.execute(query)
        row = self.cursor.fetchone()
        return row["url_id"]

    def update_db(self, website_name: str, recipe_info_dict: Dict) -> None:
        url_query = f"""
                    INSERT INTO keto_recipe_urls(url, website_name)
                    VALUES (%s, '{website_name}')
                    ON DUPLICATE KEY UPDATE url=VALUES(url), website_name=VALUES(website_name);
                """
        self.cursor.executemany(url_query, recipe_info_dict["web_crawling_url_list"])
        id_query = f"""
                    INSERT INTO keto_recipe_urls(post_id, website_name)
                    VALUES (%s, '{website_name}')
                    ON DUPLICATE KEY UPDATE post_id=VALUES(post_id), website_name=VALUES(website_name);
                """
        self.cursor.executemany(id_query, recipe_info_dict["api_crawling_id_list"])
        self.db.commit()
        logging.info("Successfully updated recipe url DB")

    def get_web_url_list(self, website_name: str) -> List[str]:
        query = f"""
                    SELECT url from keto_recipe_urls where website_name='{website_name}'
                """
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        return [
            data["url"]
            for data in rows
            if data["url"] is not None and data["url"] not in EXCEPTION_URLS
        ]

    def get_new_web_url_list(self, website_name: str) -> List[str]:
        query = f"""
                    SELECT url from keto_recipe_urls where website_name='{website_name}'
                    AND url_id not in (select url_id from keto_recipe)
                """
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        return [
            data["url"]
            for data in rows
            if data["url"] is not None and data["url"] not in EXCEPTION_URLS
        ]

    def get_api_id_list(self, website_name: str) -> List[str]:
        query = f"""
                    SELECT post_id from keto_recipe_urls where website_name='{website_name}'
                """
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        return [data["post_id"] for data in rows if data["post_id"] is not None]

    def insert_into_keto_recipe(self, keto_recipe_info_list: List[Dict]) -> None:
        try:
            query = f"""
                        INSERT IGNORE INTO
                        keto_recipe(
                            recipe_name, url_id, yield, yield_unit,
                            prep_time, active_time, total_time, image_url
                        )
                        VALUES (
                                %(recipe_name)s, %(url_id)s, %(yield)s, %(yield_unit)s, %(prep_time)s,
                                 %(active_time)s, %(total_time)s, %(image_url)s
                                )
                    """
            self.cursor.executemany(query, (keto_recipe_info_list))
            logging.info(f"Successfully inserted into keto_recipe")
        except Exception as e:
            logging.error(f"{e} -> keto_recipe")
            raise e

    def insert_into_keto_recipe_ingredients(
        self, keto_recipe_ingredients_list: List[List], website_name: str
    ):
        try:
            for ingredients_list in keto_recipe_ingredients_list:
                recipe_id = self.get_recipe_id_by_recipe_and_website_name(
                    recipe_name=ingredients_list[0]["recipe_name"],
                    website_name=website_name,
                )
                query = f"""
                            INSERT IGNORE INTO
                            keto_recipe_ingredients(recipe_id, ingredient_name, amount, unit)
                            VALUES ({recipe_id}, %(ingredient_name)s, %(amount)s, %(unit)s)
                        """
                self.cursor.executemany(query, ingredients_list)
            logging.info(f"Successfully inserted into keto_recipe_ingredients")
        except Exception as e:
            logging.error(f"{e} -> keto_recipe_ingredients")
            raise e

    def insert_into_keto_recipe_instructions(
        self, keto_recipe_instructions_list: List[List], website_name: str
    ):
        try:
            for instructions_list in keto_recipe_instructions_list:
                recipe_id = self.get_recipe_id_by_recipe_and_website_name(
                    recipe_name=instructions_list[0]["recipe_name"],
                    website_name=website_name,
                )
                query = f"""
                            INSERT IGNORE INTO
                            keto_recipe_instructions(recipe_id, order_number, eng_description)
                            VALUES ({recipe_id}, %(order_number)s, %(eng_description)s)
                        """
                self.cursor.executemany(query, instructions_list)
            logging.info(f"Successfully inserted into keto_recipe_instructions")
        except Exception as e:
            logging.error(f"{e} -> keto_recipe_instructions")
            raise e

    def insert_into_keto_recipe_nutrition(
        self, keto_recipe_nutrition_list: List[Dict], website_name: str
    ):
        try:
            for nutrition_dict in keto_recipe_nutrition_list:
                recipe_id = self.get_recipe_id_by_recipe_and_website_name(
                    recipe_name=nutrition_dict["recipe_name"], website_name=website_name
                )
                query = f"""
                            INSERT IGNORE INTO
                            nutrition(recipe_id, energy, carbohydrate, fat, protein, total_dietary_fiber)
                            VALUES (
                                {recipe_id}, %(energy)s, %(carbohydrate)s, %(fat)s, %(protein)s, %(total_dietary_fiber)s
                            )
                        """
                self.cursor.execute(query, nutrition_dict)
            logging.info(f"Successfully inserted into keto_recipe_nutrition")
        except Exception as e:
            logging.error(f"{e} -> keto_recipe_nutrition")
            raise e

    def insert_all_into_db(
        self, recipe_dict_list: List[Dict], website_name: str
    ) -> None:
        try:
            self.insert_into_keto_recipe(
                keto_recipe_info_list=[
                    recipe_dict["keto_recipe_info"] for recipe_dict in recipe_dict_list
                ]
            )
            self.insert_into_keto_recipe_ingredients(
                keto_recipe_ingredients_list=[
                    recipe_dict["keto_recipe_ingredients"]
                    for recipe_dict in recipe_dict_list
                ],
                website_name=website_name,
            )
            self.insert_into_keto_recipe_instructions(
                keto_recipe_instructions_list=[
                    recipe_dict["keto_recipe_instructions"]
                    for recipe_dict in recipe_dict_list
                ],
                website_name=website_name,
            )
            self.insert_into_keto_recipe_nutrition(
                keto_recipe_nutrition_list=[
                    recipe_dict.get("keto_recipe_nutrition")
                    for recipe_dict in recipe_dict_list
                    if recipe_dict.get("keto_recipe_nutrition") is not None
                ],
                website_name=website_name,
            )
            self.db.commit()
        except Exception as e:
            logging.error(e)
            self.db.rollback()
        finally:
            self.db.close()
