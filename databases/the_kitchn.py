import logging

from constants import WebsiteNames
from crawlers.the_kitchn import get_total_recipe_dict_list
from databases.db import BaseRecipeDB

logging.root.setLevel(logging.INFO)


if __name__ == "__main__":
    recipe_dict_list = get_total_recipe_dict_list()
    db = BaseRecipeDB()
    db.insert_all_into_db(
        recipe_dict_list=recipe_dict_list, website_name=WebsiteNames.THE_KITCHN.value
    )
