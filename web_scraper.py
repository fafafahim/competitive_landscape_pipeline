import os  
import logging  
import requests  
import asyncio  
import json  
from urllib.parse import urljoin, urlparse  
from PIL import Image  
import pytesseract  
from playwright.async_api import async_playwright  
  
class WebScraper:  
    def __init__(self):  
        self.bing_api_key = os.getenv("BING_SEARCH_API_KEY")  
        if not self.bing_api_key:  
            raise ValueError("BING_SEARCH_API_KEY is not set in environment variables.")  
  
    def fetch_or_search_company_website(self, company_name, websites_dict):  
        """  
        Fetch company website from a dictionary or perform a Bing search.  
        """  
        logging.info(f"Fetching website for {company_name}")  
        website = websites_dict.get(company_name)  
  
        if not website:  
            logging.info(f"Website not found in provided data for {company_name}. Performing Bing search.")  
            website = self.search_company_website(company_name)  
  
        website = self.sanitize_url(website)  
        if not self.is_valid_url(website):  
            logging.error(f"Invalid URL for {company_name}: {website}")  
            return "Website not found."  
  
        logging.info(f"Found website for {company_name}: {website}")  
        return website  
  
    def search_company_website(self, company_name):  
        """  
        Use Bing Search API to find the company's official website.  
        """  
        try:  
            endpoint = "https://api.bing.microsoft.com/v7.0/search"  
            headers = {"Ocp-Apim-Subscription-Key": self.bing_api_key}  
            params = {"q": f"{company_name} official website", "count": 1}  
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)  
            response.raise_for_status()  
            search_results = response.json()  
            if "webPages" in search_results and search_results["webPages"]["value"]:  
                website = search_results["webPages"]["value"][0]["url"]  
                logging.info(f"Bing search found website for {company_name}: {website}")  
                return website  
            else:  
                logging.warning(f"No website found in Bing search results for {company_name}")  
                return "Website not found."  
        except Exception as e:  
            logging.error(f"Error finding website for {company_name}: {e}")  
            return "Website not found."  
  
    @staticmethod  
    def sanitize_url(url):  
        """  
        Ensure the URL is properly formatted with scheme and no extra quotes.  
        """  
        url = url.strip().strip('"').strip("'")  
        if not url.lower().startswith(("http://", "https://")):  
            url = "https://" + url  
        return url  
  
    @staticmethod  
    def is_valid_url(url):  
        """  
        Validate the URL format.  
        """  
        try:  
            result = urlparse(url)  
            return all([result.scheme, result.netloc])  
        except ValueError:  
            return False  
  
    @staticmethod  
    def perform_ocr_on_image(image_path):  
        """  
        Perform OCR on the given image and return the extracted text.  
        """  
        try:  
            image = Image.open(image_path)  
            text = pytesseract.image_to_string(image)  
            logging.info(f"OCR text extracted from {image_path}")  
            return text  
        except Exception as e:  
            logging.error(f"Error performing OCR on {image_path}: {e}")  
            return ""  
  
    async def extract_dynamic_content_with_playwright_async(self, url, screenshot_dir, delay_seconds=5):  
        """  
        Extract full HTML content from JavaScript-rendered pages using Playwright Async API.  
        Scrolls the page to ensure all elements are loaded, then takes a screenshot and performs OCR.  
        """  
        logging.info(f"Extracting dynamic content from {url}")  
        try:  
            async with async_playwright() as p:  
                browser = await p.chromium.launch(headless=True)  
                context = await browser.new_context(  
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"  
                )  
                page = await context.new_page()  
                await page.goto(url, wait_until='networkidle', timeout=120000)  
  
                # Scroll down the page incrementally  
                previous_height = None  
                while True:  
                    current_height = await page.evaluate('() => document.body.scrollHeight')  
                    if previous_height == current_height:  
                        break  
                    previous_height = current_height  
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')  
                    # Wait for new content to load  
                    await asyncio.sleep(1)  
  
                # Wait for additional seconds to allow dynamic content to load  
                await asyncio.sleep(delay_seconds)  
  
                content = await page.content()  
  
                # Take screenshot  
                parsed_url = urlparse(url)  
                safe_path = parsed_url.path.replace('/', '_').strip('_') or 'home'  
                screenshot_filename = f"{parsed_url.netloc}_{safe_path}.png"  
                screenshot_path = os.path.join(screenshot_dir, screenshot_filename)  
                await page.screenshot(path=screenshot_path, full_page=True)  
                logging.info(f"Screenshot saved to {screenshot_path}")  
  
                await context.close()  
                await browser.close()  
  
                # Perform OCR on the screenshot  
                ocr_text = self.perform_ocr_on_image(screenshot_path)  
                logging.info(f"OCR text extracted from screenshot of {url}")  
  
                return content, ocr_text  
  
        except Exception as e:  
            logging.error(f"Error processing {url} with Playwright: {e}")  
            return "", ""  
  
    def search_bing_web(self, query):  
        """  
        Perform a web search using Bing Search API and return the search results snippets.  
        """  
        logging.info(f"Performing Bing web search for query: {query}")  
        try:  
            endpoint = "https://api.bing.microsoft.com/v7.0/search"  
            headers = {"Ocp-Apim-Subscription-Key": self.bing_api_key}  
            params = {  
                "q": query,  
                "count": 5,  # Number of results to fetch  
                "textDecorations": False,  
                "textFormat": "Raw",  
            }  
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)  
            response.raise_for_status()  
            search_results = response.json()  
            snippets = []  
            if "webPages" in search_results and search_results["webPages"]["value"]:  
                for result in search_results["webPages"]["value"]:  
                    snippet = result.get("snippet", "")  
                    url = result.get("url", "")  
                    snippets.append({"url": url, "snippet": snippet})  
            else:  
                logging.warning(f"No web pages found in Bing search results for query: {query}")  
            return snippets  
        except Exception as e:  
            logging.error(f"Error performing Bing web search for query '{query}': {e}")  
            return []  