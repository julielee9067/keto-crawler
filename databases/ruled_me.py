import logging
from typing import Dict, List

from constants import WebsiteNames
from crawlers.ruled_me import get_total_recipe_dict_list
from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)


class RuledMeDB(BaseRecipeDB):
    def insert_into_keto_recipe(self, recipe_dict_sublist: List[Dict]):
        try:
            query_list = [
                (
                    recipe["recipe_name"],
                    recipe["yield"],
                    recipe["url_id"],
                    recipe["yield_unit"],
                    recipe["image_url"],
                )
                for recipe in recipe_dict_sublist
            ]
            query = f"""
                        INSERT IGNORE INTO keto_recipe(recipe_name, yield, url_id, yield_unit, image_url)
                        VALUES (%s, %s, %s, %s, %s)
                    """
            logging.info(f"Ruled Me: Successfully inserted into keto_recipe")
            self.cursor.executemany(query, query_list)
        except Exception as e:
            logging.error(f"Ruled Me: {e} -> keto_recipe")
            raise e

    def insert_into_keto_recipe_ingredients(
        self, recipe_dict_sublist: List[Dict], website_name: str
    ):
        try:
            query_list = [
                (
                    ingredient,
                    self.get_recipe_id_by_recipe_and_website_name(
                        recipe_name=recipe["recipe_name"], website_name=website_name
                    ),
                )
                for recipe in recipe_dict_sublist
                if recipe.get("ingredients") is not None
                for ingredient in recipe["ingredients"]
            ]
            query = f"""
                        INSERT IGNORE INTO keto_recipe_ingredients(ingredient_name, recipe_id)
                        VALUES (%s, %s)
                    """
            logging.info(
                f"Ruled Me: Successfully inserted into keto_recipe_ingredients"
            )
            self.cursor.executemany(query, query_list)
        except Exception as e:
            logging.error(f"Ruled Me: {e} -> keto_recipe_ingredients")
            raise e

    def insert_into_keto_recipe_instructions(
        self, recipe_dict_sublist: List[Dict], website_name: str
    ):
        try:
            query_list = [
                (
                    self.get_recipe_id_by_recipe_and_website_name(
                        recipe_name=recipe["recipe_name"], website_name=website_name
                    ),
                    index,
                    instruction.strip(),
                )
                for recipe in recipe_dict_sublist
                if recipe.get("instructions") is not None
                for index, instruction in enumerate(recipe["instructions"])
            ]
            query = f"""
                        INSERT IGNORE INTO keto_recipe_instructions(recipe_id, order_number, eng_description)
                        VALUES (%s, %s, %s)
                    """
            logging.info(
                f"Ruled Me: Successfully inserted into keto_recipe_instructions"
            )
            self.cursor.executemany(query, query_list)
        except Exception as e:
            logging.error(f"Ruled Me: {e} -> keto_recipe_instructions")
            raise e

    def insert_into_keto_recipe_nutrition(
        self, recipe_dict_sublist: List[Dict], website_name: str
    ):
        try:
            query_list = [
                (
                    self.get_recipe_id_by_recipe_and_website_name(
                        recipe["recipe_name"], website_name=website_name
                    ),
                    recipe["nutrition"]["energy"],
                    recipe["nutrition"]["fat"],
                    recipe["nutrition"]["net_carbs"],
                    recipe["nutrition"]["total_dietary_fiber"],
                    recipe["nutrition"]["protein"],
                )
                for recipe in recipe_dict_sublist
                if recipe.get("nutrition") is not None
            ]
            query = f"""
                        INSERT IGNORE INTO nutrition(recipe_id, energy, fat, carbohydrate, total_dietary_fiber, protein)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
            logging.info(f"Ruled Me: Successfully inserted into keto_recipe_nutrition")
            self.cursor.executemany(query, query_list)
        except Exception as e:
            logging.error(f"Ruled Me: {e} -> keto_recipe_nutrition")
            raise e

    def run(self):
        recipe_dict_list = get_total_recipe_dict_list()
        for i in range(0, len(recipe_dict_list), 100):
            try:
                recipe_dict_sublist = recipe_dict_list[i : i + 100]
                self.insert_into_keto_recipe(recipe_dict_sublist)
                self.insert_into_keto_recipe_instructions(
                    recipe_dict_sublist, WebsiteNames.RULED_ME.value
                )
                self.insert_into_keto_recipe_ingredients(
                    recipe_dict_sublist, WebsiteNames.RULED_ME.value
                )
                self.insert_into_keto_recipe_nutrition(
                    recipe_dict_sublist, WebsiteNames.RULED_ME.value
                )
                logging.info(
                    f"Inserted {i+len(recipe_dict_sublist)}/{len(recipe_dict_list)}"
                )
                self.db.commit()
            except Exception as e:
                logging.error(f"Ruled Me: {e}")
                self.db.rollback()
        self.db.close()


if __name__ == "__main__":
    db = RuledMeDB()
    db.run()
