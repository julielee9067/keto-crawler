import logging
from typing import Dict, List

from constants import WebsiteNames
from crawlers.keto_diet import get_total_recipe_dict_list
from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)


class KetoDietDB(BaseRecipeDB):
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
                            nutrition(recipe_id, energy, carbohydrate, fat, protein, total_dietary_fiber, etc)
                            VALUES (
                                {recipe_id}, %(energy)s, %(carbohydrate)s, %(fat)s,
                                %(protein)s, %(total_dietary_fiber)s, %(etc)s
                            )
                        """
                self.cursor.execute(query, nutrition_dict)
            logging.info(f"Successfully inserted into keto_recipe_nutrition")
        except Exception as e:
            logging.error(f"{e} -> keto_recipe_nutrition")
            raise e


if __name__ == "__main__":
    total_recipe_dict_list = get_total_recipe_dict_list()
    db = KetoDietDB()
    db.insert_all_into_db(
        recipe_dict_list=total_recipe_dict_list,
        website_name=WebsiteNames.KETO_DIET.value,
    )
