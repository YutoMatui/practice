import json
import re
from google import genai
from utils import setup_logger, clean_html_for_ai

class AIHandler:
    def __init__(self, api_key: str, model_name: str):
        self.logger = setup_logger("AI_Agent")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def _call_gemini(self, prompt: str) -> str:
        """
        APIコールを実行する。レート制限待機コードは削除済み。
        """
        try:
            # Docker等の環境によってはSSL証明書エラーが出る場合があるため、必要ならここでVerify設定等を行う
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt
            )
            return response.text
        except Exception as e:
            self.logger.error(f"Gemini API Error: {e}")
            return ""

    def parse_json(self, text: str) -> dict:
        try:
            # コードブロック ```json ... ``` がある場合と、生のJSONの場合両方に対応
            json_match = re.search(r'(\{.*\})', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
        except Exception as e:
            self.logger.error(f"JSON解析失敗: {e}")
        return {}

    def analyze_list_page(self, html: str) -> dict:
        """
        リストページから情報を抽出。
        可能な限りこの段階で amount や deadline などの情報も取得してしまう。
        """
        cleaned_html = clean_html_for_ai(html)
        prompt = f"""
        以下のHTMLは助成金や公募のリストページです。ここから各記事の情報を抽出してください。
        
        【重要指示】
        - 「すべての項目を埋める」ことが最優先です。
        - 各記事の個別詳細ページへのURL（tender-details, opportunity-details などを含むURL）を必ず見つけてください。
        - リスト上に金額(amount)や期限(date)、要約などが表示されている場合は、必ず抽出してください。
        - **どうしても記載がない項目のみ "不明" としてください。**
        
        【抽出項目】
        - URL, title
        - issuingOrganization (発行組織)
        - amount (金額情報)
        - publicationDate (日付情報 MM-dd-yyyy)
        - articleType (Open/Closedなど)

        【ページネーション】
        - 次へ進むボタンのCSSセレクタ (next_page_selector)

        【回答形式 JSON】
        {{
          "articles": [ 
             {{ 
               "url": "...", "title": "...", "issuingOrganization": "...", 
               "amount": "...", "publicationDate": "...", "articleType": "..." 
             }} 
          ],
          "next_page_selector": "csv_selector_string"
        }}

        HTML:
        {cleaned_html}
        """
        return self.parse_json(self._call_gemini(prompt))

    def extract_details(self, html: str) -> dict:
        """
        詳細ページ解析。
        深掘り用のリンクを最大3つまで取得する。
        """
        cleaned_html = clean_html_for_ai(html)
        
        prompt = f"""
        Webスクレイピングの専門家として、以下のHTMLから公募の詳細情報を余すところなく抽出してください。
        「すべての値を埋める」ことが義務付けられています。

        【抽出・記述ルール】
        1. 以下のJSONスキーマにある全ての項目を埋めてください。
        2. **特定の数値や日付が明記されていない場合でも、関連する記述（例：「予算はプロジェクト毎に決定」「期間は3年間」など）があればそれを記述してください。**
        3. 候補が複数ある場合は最も新しいもの、または全体を代表するものを選択してください。
        4. 日付は MM-dd-yyyy 形式。特定できない場合は年度（例：01-01-2025）や、関連する日付を記述。
        5. summaryは日本語で要約。それ以外は原文のまま。
        6. **「不明」と出力するのは、HTML内にその項目に関連する情報が一切、1文字も存在しない場合のみに限定してください。**

        【深掘りリンクの探索】
        情報が一つでも「不明」である場合、より詳細な情報（Full Announcement, Guidelines, PDF link, FAQなど）が載っていそうなリンクをHTML内から探し、
        **最も情報が補完できそうな順にランク付けして上位3つまで** "next_deep_links" リストに含めてください。
        特に、EUの公募サイトでは "Call Document" や "Draft", "Full text" といった単語が含まれるPDFリンクを最優先してください。

        【出力フォーマット】
        {{
            "extracted_data": {{
                "title": "公募タイトル",
                "issuingOrganization": "発行組織",
                "summary": "日本語要約",
                "articleType": "Open/Closed/Forecasted/Misc",
                "publicationDate": "MM-dd-yyyy",
                "country": "ISO 2文字",
                "amount": "金額(単位含む、または予算に関する記述)",
                "funder": "資金提供者",
                "fundingType": "Grant/Contract/etc",
                "researchStartDate": "MM-dd-yyyy",
                "researchEndDate": "MM-dd-yyyy",
                "field": "分野",
                "keywords": "カンマ区切り",
                "description": "詳細説明（予算や期間の補足情報も含む）"
            }},
            "next_deep_links": ["URL1", "URL2", "URL3"]
        }}

        HTML:
        {cleaned_html}
        """
        
        return self.parse_json(self._call_gemini(prompt))
