import logging
import sys
import csv
import io
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

def setup_logger(name="AI_Crawler") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def clean_html_for_ai(html_content: str) -> str:
    """トークン節約と精度向上のためHTMLを整形。PDFから抽出したテキストなどの場合はそのまま返す。"""
    if not html_content:
        return ""
    
    # HTMLタグが含まれているか簡易チェック
    if "<html" not in html_content.lower() and "<body" not in html_content.lower() and "<div" not in html_content.lower():
        # HTMLではない（PDFから抽出したテキスト等）と判断し、整形せず返す
        return html_content[:90000]

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # ノイズとなるタグを削除
    for tag in soup(["script", "style", "noscript", "svg", "path", "header", "footer", "iframe", "meta", "button", "input"]):
        tag.decompose()

    # 特定のドメインや定型的なリンク集を排除（EUサイトのフッター対策）
    for link in soup.find_all("a", href=True):
        href = link['href'].lower()
        if any(x in href for x in ["facebook.com", "twitter.com", "linkedin.com", "instagram.com", "youtube.com"]):
            link.decompose()
    
    # テキストを整形して返す
    cleaned = " ".join(str(soup.body if soup.body else soup).split())
    return cleaned[:90000] # モデルの許容量に合わせて調整

def extract_text_from_pdf(url: str) -> str:
    """URLからPDFをダウンロードしてテキストを抽出する"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # メモリ上でPDFを開く
        pdf_stream = io.BytesIO(response.content)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        
        text = ""
        for page in doc:
            text += page.get_text()
        
        doc.close()
        return text
    except Exception as e:
        print(f"PDF抽出エラー ({url}): {e}")
        return ""

def save_data_to_csv(data_list: list, filename: str):
    if not data_list:
        return
    try:
        # 全ての辞書からキーの和集合を取得してヘッダーにする
        all_keys = set().union(*(d.keys() for d in data_list))
        # 順序を保つためにリスト化（重要な項目を先頭に）
        priority_order = ["title", "url", "amount", "summary", "articleType", "description"]
        fieldnames = [k for k in priority_order if k in all_keys] + [k for k in all_keys if k not in priority_order]

        with open(filename, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data_list)
    except Exception as e:
        print(f"CSV保存エラー: {e}")
