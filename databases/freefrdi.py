import logging
from typing import Dict, List

from constants import WebsiteNames
from crawlers.freefrdi import get_total_recipe_dict_list
from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)


class FreeFrdiDB(BaseRecipeDB):
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
                            keto_recipe_instructions(recipe_id, order_number, kor_description)
                            VALUES ({recipe_id}, %(order_number)s, %(kor_description)s)
                        """
                self.cursor.executemany(query, instructions_list)
            logging.info(f"Successfully inserted into keto_recipe_instructions")
        except Exception as e:
            logging.error(f"{e} -> keto_recipe_instructions")
            raise e

    def insert_into_keto_recipe_tips(
        self, keto_recipe_tips_list: List[List], website_name: str
    ):
        try:
            for tips_list in keto_recipe_tips_list:
                if tips_list is None:
                    continue

                recipe_id = self.get_recipe_id_by_recipe_and_website_name(
                    recipe_name=tips_list[0]["recipe_name"],
                    website_name=website_name,
                )
                query = f"""
                            INSERT IGNORE INTO
                            keto_recipe_tips(recipe_id, order_number, tip)
                            VALUES ({recipe_id}, %(order_number)s, %(tip)s)
                        """
                self.cursor.executemany(query, tips_list)
            logging.info(f"Successfully inserted into keto_recipe_tips")
        except Exception as e:
            logging.error(f"{e} -> keto_recipe_tips")
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
            self.insert_into_keto_recipe_tips(
                keto_recipe_tips_list=[
                    recipe_dict["keto_recipe_tips"] for recipe_dict in recipe_dict_list
                ],
                website_name=website_name,
            )
            self.db.commit()
        except Exception as e:
            logging.error(e)
            self.db.rollback()
        finally:
            self.db.close()


if __name__ == "__main__":
    recipe_dict_list = get_total_recipe_dict_list()
    db = FreeFrdiDB()
    db.insert_all_into_db(
        recipe_dict_list=recipe_dict_list,
        website_name=WebsiteNames.FREE_FRDI.value,
    )
