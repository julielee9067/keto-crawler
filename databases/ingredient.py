import json
import re
from typing import List

from api import parse_nutrition_api
from constants import NUTRITION_COLUMN_NAMES
from databases.db import BaseDBConnection


class IngredientDB(BaseDBConnection):
    def add_ingredient_info(self):
        """
        Insert base ingredient information (kor_ingredient_name, eng_ingredient_name)
        into ingredient table.
        :return:
        """
        ingredient_list = parse_nutrition_api()
        query_list = [
            (ingredient["fdNm"], ingredient["fdEngNm"])
            for ingredient in ingredient_list
        ]
        query = f"""
                    INSERT IGNORE INTO ingredient(kor_ingredient_name, eng_ingredient_name)
                    VALUES (%s, %s)
                """
        self.cursor.executemany(query, query_list)
        nutrition_list = [
            {
                "food_name": ingredient["fdNm"],
                "nutrition_info": [
                    {
                        "nutrition_group": nutrition["irdntSeNm"],
                        "nutrition_detail": nutrition["irdnttcket"],
                    }
                    for nutrition in ingredient["irdnt"]
                ],
            }
            for ingredient in ingredient_list
        ]

        self.add_ingredient_nutrition_info(nutrition_list=nutrition_list)
        self.db.commit()

    def get_ingredient_id_by_name(self, ingredient_name: str) -> str:
        """
        Get ingredient_id by the ingredient name.

        :param ingredient_name: str
        :return:
        """
        query = f"""
                    SELECT ingredient_id from ingredient where kor_ingredient_name='{ingredient_name}'
                """
        self.cursor.execute(query)
        row = self.cursor.fetchone()
        return row["ingredient_id"]

    def add_ingredient_nutrition_info(self, nutrition_list: List):
        """
        Insert detailed nutrition information into nutrition table.

        :param nutrition_list: List
        :return:
        """
        query_list = list()
        for nutrition in nutrition_list:
            query_dict = dict()
            for nutrition_info in nutrition["nutrition_info"]:
                if nutrition_info["nutrition_group"] == "일반성분":
                    query_dict = {
                        detail["irdntEngNm"]
                        .lower()
                        .replace(" ", "_"): re.findall(
                            r"\d*\.\d+|\d+", detail["contInfo"].replace("-", "0")
                        )[0]
                        if re.findall(r"\d*\.\d+|\d+", detail["contInfo"])
                        else "0"
                        for detail in nutrition_info["nutrition_detail"]
                    }
                else:
                    json_obj = {
                        NUTRITION_COLUMN_NAMES[
                            nutrition_info["nutrition_group"]
                        ]: json.dumps(
                            nutrition_info["nutrition_detail"], ensure_ascii=False
                        )
                    }
                    query_dict.update(json_obj)
            query_dict.update(
                {
                    "ingredient_id": self.get_ingredient_id_by_name(
                        ingredient_name=nutrition["food_name"]
                    ),
                    "amount": 100,
                }
            )
            query_list.append(query_dict)

        query = f"""
                    INSERT IGNORE INTO nutrition
                    (
                        energy, water, protein, fat, ash, carbohydrate, totalsugars, sucrose, glucose, fructose,
                        lactose, maltose, galactose, total_dietary_fiber, water_soluble_dietary_fiber,
                        water_insoluble_dietary_fiber, amino_acids, fatty_acids, minerals, vitamins,
                        etc, ingredient_id, amount
                    )
                    VALUES
                    (
                        %(energy)s, %(water)s, %(protein)s, %(fat)s, %(ash)s, %(carbohydrate)s, %(totalsugars)s,
                        %(sucrose)s, %(glucose)s, %(fructose)s, %(lactose)s, %(maltose)s, %(galactose)s,
                        %(total_dietary_fiber)s, %(water_soluble_dietary_fiber)s,
                        %(water_insoluble_dietary_fiber)s, %(amino_acids)s, %(fatty_acids)s, %(minerals)s, %(vitamins)s,
                        %(etc)s, %(ingredient_id)s, %(amount)s
                    )
                """
        self.cursor.executemany(query, query_list)
        self.db.commit()

    def add_nutrition_unit_info(self, nutrition_list: List):
        """
        Insert nutrition unit information into nutrition_unit table.
        This is for ONE_TIME execution only.

        :param nutrition_list: List
        :return:
        """
        unit_list = [
            (nutrition["irdntEngNm"], nutrition["irdntUnitNm"])
            for nutrition in nutrition_list
        ]
        query = f"""
                    INSERT IGNORE INTO nutrition_unit(nutrition_name, unit)
                    VALUES (%s, %s)
                """
        self.cursor.executemany(query, unit_list)
        self.db.commit()


if __name__ == "__main__":
    db = IngredientDB()
    db.add_ingredient_info()
