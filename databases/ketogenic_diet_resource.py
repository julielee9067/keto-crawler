import logging
from typing import Dict, List

from constants import WebsiteNames
from crawlers.ketogenic_diet_resource import get_total_recipe_dict_list
from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)


class KetogenicDietResourceDB(BaseRecipeDB):
    def insert_all_into_db(self, recipe_dict_list: List[Dict], website_name: str):
        try:
            self.insert_into_keto_recipe(
                keto_recipe_info_list=[
                    recipe_info
                    for recipe_dict in recipe_dict_list
                    for recipe_info in recipe_dict["keto_recipe_info"]
                ]
            )
            self.insert_into_keto_recipe_ingredients(
                keto_recipe_ingredients_list=[
                    ingredients_info
                    for recipe_dict in recipe_dict_list
                    for ingredients_info in recipe_dict["keto_recipe_ingredients"]
                ],
                website_name=website_name,
            )
            self.insert_into_keto_recipe_instructions(
                keto_recipe_instructions_list=[
                    instructions_info
                    for recipe_dict in recipe_dict_list
                    for instructions_info in recipe_dict["keto_recipe_instructions"]
                    if instructions_info
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
    db = KetogenicDietResourceDB()
    db.insert_all_into_db(
        recipe_dict_list=recipe_dict_list,
        website_name=WebsiteNames.KETOGENIC_DIET_RESOURCE.value,
    )
