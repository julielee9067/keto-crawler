import logging

from constants import WebsiteNames
from crawlers.aussie_keto_queen import get_total_recipe_dict_list
from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)


if __name__ == "__main__":
    total_recipe_dict_list = get_total_recipe_dict_list()
    db = BaseRecipeDB()
    db.insert_all_into_db(
        recipe_dict_list=total_recipe_dict_list,
        website_name=WebsiteNames.AUSSIE_KETO_QUEEN.value,
    )
