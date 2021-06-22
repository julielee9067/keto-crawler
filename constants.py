import enum
import re

EXCEPTION_URLS = [
    "https://www.ketogenic-diet-resource.com/low-carb-mixed-drinks.html",
    "https://freefrdi.com/imketo-coconut-tortilla/",
]


class WebsiteNames(enum.Enum):
    THE_BEST_KETO_RECIPE = "the best keto recipe"
    RULED_ME = "ruled me"
    THE_GIRL_WHO_ATE_EVERYTHING = "the girl who ate everything"
    FAMILY_ON_KETO = "family on keto"
    AUSSIE_KETO_QUEEN = "aussie keto queen"
    THE_KITCHN = "the kitchn"
    LOW_CARB_MAVEN = "low carb maven"
    KETO_DIET = "keto diet"
    KETOGENIC_DIET_RESOURCE = "ketogenic diet resource"
    CHARLIE_FOUNDATION = "charlie foundation"
    TEN_THOUSAND_RECIPE = "ten thousand recipe"
    FREE_FRDI = "freefrdi"
    KETO_PEOPLE = "keto people"


class BaseUrls(enum.Enum):
    THE_BEST_KETO_RECIPE = "https://thebestketorecipes.com/"
    THE_GIRL_WHO_ATE_EVERYTHING = "https://www.the-girl-who-ate-everything.com/"
    RULED_ME = "https://www.ruled.me/"
    FAMILY_ON_KETO = "https://familyonketo.com/"
    AUSSIE_KETO_QUEEN = "https://aussieketoqueen.com/"
    THE_KITCHN = "https://www.thekitchn.com/"
    LOW_CARB_MAVEN = "https://www.lowcarbmaven.com/"
    KETO_DIET = "https://ketodietapp.com/"
    KETOGENIC_DIET_RESOURCE = "https://www.ketogenic-diet-resource.com/"
    CHARLIE_FOUNDATION = "https://charliefoundation.org/"
    TEN_THOUSAND_RECIPE = "https://www.10000recipe.com/"
    FREE_FRDI = "https://freefrdi.com/"
    KETO_PEOPLE = "https://ketopeople.co.kr/"


NUTRITION_COLUMN_NAMES = {
    "아미노산": "amino_acids",
    "지방산": "fatty_acids",
    "무기질": "minerals",
    "비타민": "vitamins",
    "기타": "etc",
}

USER_AGENT_LIST = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        "Chrome/74.0.3729.169 Safari/537.36"
    ),
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/74.0.3729.157 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/60.0.3112.113 Safari/537.36"
    ),
    "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.71 Safari/537.36",
]

INGREDIENT_COLUMN_NAMES = {
    "fdNm": "kor_ingredient_name",
    "fdEngNm": "eng_ingredient_name",
    "food_groups": "fdGrupp",
}

RULED_ME_NUTRITION_COLUMN_LIST = [
    "nutrition",
    "energy",
    "fat",
    "carbohydrate",
    "total_dietary_fiber",
    "net_carbs",
    "protein",
]

EMOJI_PATTERN = re.compile(
    "["
    u"\U0001F600-\U0001F64F"  # emoticons
    u"\U0001F300-\U0001F5FF"  # symbols & pictographs
    u"\U0001F680-\U0001F6FF"  # transport & map symbols
    u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
    u"\U00002500-\U00002BEF"  # chinese char
    u"\U00002702-\U000027B0"
    u"\U00002702-\U000027B0"
    u"\U000024C2-\U0001F251"
    u"\U0001f926-\U0001f937"
    u"\U00010000-\U0010ffff"
    u"\u2640-\u2642"
    u"\u2600-\u2B55"
    u"\u200d"
    u"\u23cf"
    u"\u23e9"
    u"\u231a"
    u"\ufe0f"  # dingbats
    u"\u3030"
    "]+",
    flags=re.UNICODE,
)

NUTRITION_API_PAGE_SIZE = 500
TOTAL_NUTRITION_COUNT = 3089
