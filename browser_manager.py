import sys
import time
import re
import subprocess
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import setup_logger, extract_text_from_pdf

class BrowserManager:
    def __init__(self, headless=True):
        self.logger = setup_logger("Browser")
        self.driver = self._create_driver(headless)

    def wait_for_element(self, css_selector: str, timeout: int = 15) -> bool:
        """特定の要素が表示されるまで待機"""
        if not self.driver: return False
        try:
            self.logger.info(f"Waiting for element: {css_selector}")
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
            )
            return True
        except Exception as e:
            self.logger.warning(f"Wait timeout: {css_selector}")
            return False

    def _get_chrome_major_version(self):
        """システムにインストールされているChromeのメジャーバージョンを取得"""
        try:
            if sys.platform == "win32":
                cmd = r'reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version'
                output = subprocess.check_output(cmd, shell=True).decode()
                version_match = re.search(r'(\d+)\.', output)
                if version_match:
                    return int(version_match.group(1))
            else:
                # Linux (Docker) 環境
                output = subprocess.check_output(['google-chrome', '--version']).decode()
                version_match = re.search(r'Chrome (\d+)\.', output)
                if version_match:
                    return int(version_match.group(1))
            return None
        except:
            return None

    def _create_driver(self, headless):
        """Docker/Windows環境に最適化したドライバ作成"""
        try:
            options = uc.ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--lang=ja-JP")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

            self.logger.info("ブラウザを起動しています...")
            
            major_version = self._get_chrome_major_version()
            # Windowsでは use_subprocess=True が推奨されることが多い
            use_sub = (sys.platform == "win32")
            
            return uc.Chrome(options=options, version_main=major_version, use_subprocess=use_sub)
        except Exception as e:
            self.logger.error(f"ドライバ起動失敗: {e}")
            return None

    def get_page_source(self, url: str, wait_time=4) -> str:
        if not self.driver: return ""
        try:
            # PDFリンクかどうかの判定 (簡易的に拡張子で判断)
            if url.lower().endswith(".pdf"):
                self.logger.info(f"PDF detected, extracting text: {url}")
                return extract_text_from_pdf(url)

            self.logger.info(f"Accessing: {url}")
            self.driver.get(url)
            time.sleep(wait_time)
            
            # 遷移後のURLがPDFの場合もある (Content-Typeで判断したいがSeleniumでは困難なのでURLで再チェック)
            current_url = self.driver.current_url
            if current_url.lower().endswith(".pdf"):
                self.logger.info(f"Redirected to PDF, extracting text: {current_url}")
                return extract_text_from_pdf(current_url)
                
            return self.driver.page_source
        except Exception as e:
            self.logger.error(f"ページ取得エラー ({url}): {e}")
            return ""

    def find_and_click(self, css_selector: str) -> bool:
        if not self.driver: return False
        try:
            elem = self.driver.find_element(By.CSS_SELECTOR, css_selector)
            if elem.is_displayed():
                self.driver.execute_script("arguments[0].scrollIntoView();", elem)
                time.sleep(1)
                elem.click()
                return True
        except:
            return False
        return False

    def get_current_url(self):
        return self.driver.current_url if self.driver else ""

    def cleanup(self):
        if self.driver:
            try:
                self.logger.info("ブラウザを終了しています...")
                # Windowsのハンドルエラー (WinError 6) を確実に回避するための処理
                if hasattr(self.driver, 'service') and self.driver.service:
                    try: self.driver.service.stop()
                    except: pass
                
                try: self.driver.quit()
                except OSError: pass 
                except: pass
            except:
                pass
            finally:
                self.driver = None
