import time
import atexit
from datetime import datetime
import config
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import setup_logger, extract_text_from_pdf
from browser_manager import BrowserManager
from ai_handler import AIHandler

class AIAutonomousCrawler:
    def __init__(self):
        self.logger = setup_logger()
        self.browser = BrowserManager(headless=config.HEADLESS_MODE)
        self.ai = AIHandler(config.API_KEY, config.MODEL_NAME)
        self.crawled_data = []
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = f"{config.OUTPUT_FILE_PREFIX}_{timestamp}.csv"
        
        atexit.register(self.cleanup)

    def cleanup(self):
        if self.browser:
            self.browser.cleanup()

    def is_data_complete(self, data: dict) -> bool:
        """必須項目が全て埋まっているかチェック"""
        missing = [field for field in config.REQUIRED_FIELDS if data.get(field) in ["不明", "", None]]
        if not missing:
            return True
        return False

    def process_single_article(self, initial_data: dict):
        """1つの案件を完了するまで深掘りする"""
        
        current_data = initial_data.copy()
        visited_urls = set()
        visited_urls.add(current_data['url'])

        # 1. まず詳細トップページへ行く
        self.logger.info(f"詳細解析開始: {current_data['url']}")
        html = self.browser.get_page_source(current_data['url'])
        if not html: return current_data

        # AI抽出
        result = self.ai.extract_details(html)
        extracted = result.get("extracted_data", {})
        
        # マージ
        for k, v in extracted.items():
            if v and v != "不明":
                # リストページの情報より詳細ページの情報を優先、または未定義を埋める
                current_data[k] = v

        # 完了判定
        if self.is_data_complete(current_data):
            self.logger.info("  -> 初回ページで必須情報が揃いました。")
            return current_data

        # 2. 不足している場合、深掘りリンクを試す
        deep_links = result.get("next_deep_links", [])
        # 重複除去とURLフィルタ
        valid_links = [l for l in deep_links if l.startswith("http") and l not in visited_urls]
        
        # configで設定した最大数まで試す
        for i, link in enumerate(valid_links[:config.MAX_DEEP_LINKS]):
            self.logger.info(f"  -> 深掘りリンク[{i+1}/{len(valid_links)}]: {link}")
            
            # ページ取得
            sub_html = self.browser.get_page_source(link)
            if not sub_html: continue
            visited_urls.add(link)

            # AI抽出 (プロンプトは同じものを使い、新しい情報を探させる)
            sub_result = self.ai.extract_details(sub_html)
            sub_extracted = sub_result.get("extracted_data", {})

            # マージ (既存が「不明」の場所だけ埋める)
            updated_count = 0
            for k, v in sub_extracted.items():
                if v and v != "不明" and current_data.get(k) in ["不明", "", None]:
                    current_data[k] = v
                    updated_count += 1
            
            if updated_count > 0:
                self.logger.info(f"    -> {updated_count} 項目を補完しました。")

            # 再度完了判定
            if self.is_data_complete(current_data):
                self.logger.info("  -> 全ての必須情報が揃いました。深掘りを終了します。")
                break
            
            time.sleep(2) # リンク遷移間の待機

        return current_data

    def run(self):
        if not self.browser.driver:
            self.logger.error("ブラウザドライバがありません。")
            return

        current_list_url = config.TARGET_URL
        
        try:
            for page in range(1, config.MAX_PAGES + 1):
                self.logger.info(f"=== リストページ {page} ===")
                # ページの初期読み込み（適宜待機時間を調整）
                list_html = self.browser.get_page_source(current_list_url, wait_time=7)
                
                # EUポータルなどのSPA向けに、特定のリスト要素を待つ
                # EUポータルのテンダーリストのコンテナセレクタ（例: ux-tenders-list, .tender-results-list など）
                # 汎用的に 'ux-' や 'app-' で始まるタグが多い
                self.browser.wait_for_element("ux-page-header", timeout=10) # 少なくともヘッダーが出るまで待つ
                self.browser.wait_for_element(".tender-results-list", timeout=5) # リスト自体を待つ(見つからなくても進む)
                
                # 改めて最新のソースを取得
                list_html = self.browser.driver.page_source

                # リスト解析
                analysis = self.ai.analyze_list_page(list_html)
                articles = analysis.get("articles", [])
                
                if not articles:
                    self.logger.warning("リストから案件が見つかりませんでした。HTMLのロード不足か、AIがリンクを見落とした可能性があります。")

                for art in articles:
                    url = art.get("url")
                    # URLが "不明" または無効な場合はスキップ（クラッシュ防止）
                    if not url or url == "不明" or not url.startswith("http"):
                        self.logger.warning(f"有効なURLが見つかりませんでした。スキップします: {art.get('title')}")
                        continue

                    if len(self.crawled_data) >= config.MAX_ARTICLES:
                        return

                    # リスト取得時点での初期データ作成
                    initial_data = {
                        "title": art.get("title"),
                        "url": art.get("url"),
                        "issuingOrganization": art.get("issuingOrganization", "不明"),
                        # リストページで見つかった情報があればそれを使う、なければ "不明"
                        "amount": art.get("amount", "不明"),
                        "publicationDate": art.get("publicationDate", "不明"),
                        "articleType": art.get("articleType", "不明"),
                        
                        # 未取得のフィールド
                        "summary": "不明", "country": "不明", "funder": "不明",
                        "fundingType": "不明", "researchStartDate": "不明",
                        "researchEndDate": "不明", "field": "不明",
                        "keywords": "不明", "description": "不明"
                    }

                    # 個別深掘り処理へ
                    final_data = self.process_single_article(initial_data)
                    
                    self.crawled_data.append(final_data)
                    save_data_to_csv(self.crawled_data, self.output_file)
                    
                # 次ページ
                next_sel = analysis.get("next_page_selector")
                if next_sel:
                    if not self.browser.find_and_click(next_sel):
                        break
                    time.sleep(3)
                    current_list_url = self.browser.get_current_url()
                else:
                    break

        finally:
            self.logger.info("処理完了")
            self.cleanup()

if __name__ == "__main__":
    crawler = AIAutonomousCrawler()
    crawler.run()
