import os

# --- ユーザー設定 ---
API_KEY = os.environ.get("API_KEY", "AIzaSyA2ebP8y_8jCL6PV48rDJMew0nJ_9kZqoU")
MODEL_NAME = "gemini-2.5-flash" 
TARGET_URL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-tenders?isExactMatch=true&status=31094502,31094503,31094501&order=DESC&pageNumber=1&pageSize=50&sortBy=startDate"

# --- クローラー設定 ---
MAX_PAGES = 1           # リストページをめくる最大数
MAX_ARTICLES = 5        # 取得する最大記事数
MAX_DEEP_LINKS = 3      # 1記事あたりに深掘りする最大リンク数

# --- Docker/Selenium設定 ---
# Docker環境では必ず True にする必要があります
HEADLESS_MODE = True    

# --- 出力設定 ---
# Dockerのマウントボリュームに合わせてパスを変更してください（例: "/app/output/data"）
OUTPUT_FILE_PREFIX = "crawled_data"

# --- 必須フィールド定義 ---
# これらが全て「不明」以外になるまで、またはリンクが尽きるまで深掘りを続けます
REQUIRED_FIELDS = [
    "title",
    "url",
    "issuingOrganization",
    "amount",
    "publicationDate",
    "articleType",
    "summary",
    "country",
    "funder",
    "fundingType",
    "researchStartDate",
    "researchEndDate",
    "field",
    "keywords",
    "description"
]
