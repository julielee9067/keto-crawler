import logging
from typing import List

from constants import WebsiteNames
from crawlers.ten_thousand_recipe import get_total_recipe_dict_list
from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)


class TenThousandRecipeDB(BaseRecipeDB):
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


if __name__ == "__main__":
    recipe_dict_list = get_total_recipe_dict_list()
    db = TenThousandRecipeDB()
    db.insert_all_into_db(
        recipe_dict_list=recipe_dict_list,
        website_name=WebsiteNames.TEN_THOUSAND_RECIPE.value,
    )
