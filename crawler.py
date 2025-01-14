import os  
import logging  
import requests  
import asyncio  
import json  
from urllib.parse import urljoin, urlparse  
from bs4 import BeautifulSoup  
import xml.etree.ElementTree as ET  
from data_manager import DataManager  
from web_scraper import WebScraper  
  
class Crawler:  
    def __init__(self, base_url, max_pages=20, max_depth=3, use_dynamic="playwright", screenshot_dir="screenshots"):  
        self.base_url = base_url  
        self.max_pages = max_pages  
        self.max_depth = max_depth  
        self.use_dynamic = use_dynamic  
        self.screenshot_dir = screenshot_dir  
        os.makedirs(self.screenshot_dir, exist_ok=True)  
        self.visited_urls = set()  
        self.scraper = WebScraper()  
        parsed_base_url = urlparse(self.base_url)  
        self.base_domain = f"{parsed_base_url.scheme}://{parsed_base_url.netloc}"  
        self.parsed_base_url = parsed_base_url  
  
    def fetch_sitemap_urls(self):  
        """  
        Attempt to fetch the sitemap from standard locations and parse it to extract URLs.  
        """  
        logging.info(f"Attempting to fetch sitemap for {self.base_url}")  
        possible_sitemap_urls = [  
            urljoin(self.base_domain, 'sitemap.xml'),  
            urljoin(self.base_domain, 'sitemap_index.xml'),  
            urljoin(self.base_domain, 'sitemap'),  
        ]  
        headers = {"User-Agent": "Mozilla/5.0"}  
  
        for sitemap_url in possible_sitemap_urls:  
            try:  
                response = requests.get(sitemap_url, headers=headers, timeout=10)  
                if response.status_code == 200:  
                    content_type = response.headers.get('Content-Type', '')  
                    if 'xml' in content_type or sitemap_url.endswith('.xml'):  
                        logging.info(f"Sitemap found at: {sitemap_url}")  
                        urls = self.parse_sitemap(response.text)  
                        if urls:  
                            return urls  
                        else:  
                            logging.warning(f"Sitemap at {sitemap_url} contains no URLs.")  
            except Exception as e:  
                logging.error(f"Error fetching sitemap from {sitemap_url}: {e}")  
  
        # Try to find sitemap in robots.txt  
        sitemap_urls = self.fetch_sitemap_from_robots()  
        if sitemap_urls:  
            return sitemap_urls  
  
        logging.warning(f"No sitemap found for {self.base_url}")  
        return []  
  
    def fetch_sitemap_from_robots(self):  
        """  
        Parse the robots.txt file to find the sitemap URL.  
        """  
        robots_url = urljoin(self.base_domain, 'robots.txt')  
        headers = {"User-Agent": "Mozilla/5.0"}  
        try:  
            response = requests.get(robots_url, headers=headers, timeout=10)  
            if response.status_code == 200:  
                for line in response.text.split('\n'):  
                    if line.lower().startswith('sitemap:'):  
                        sitemap_url = line.split(':', 1)[1].strip()  
                        return self.parse_sitemap_url(sitemap_url)  
        except Exception as e:  
            logging.error(f"Error fetching robots.txt from {robots_url}: {e}")  
        return []  
  
    @staticmethod  
    def parse_sitemap(xml_content):  
        """  
        Parse the sitemap XML content and extract URLs.  
        """  
        try:  
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}  
            root = ET.fromstring(xml_content)  
            urls = []  
  
            if root.tag.endswith('sitemapindex'):  
                sitemap_elements = root.findall('ns:sitemap', namespaces=namespace)  
                if sitemap_elements:  
                    logging.info(f"Found {len(sitemap_elements)} sitemaps in sitemap index.")  
                else:  
                    logging.warning("Sitemap index is empty.")  
                for sitemap in sitemap_elements:  
                    loc = sitemap.find('ns:loc', namespaces=namespace).text  
                    urls.extend(Crawler.parse_sitemap_url(loc))  
            elif root.tag.endswith('urlset'):  
                url_elements = root.findall('ns:url', namespaces=namespace)  
                if url_elements:  
                    logging.info(f"Found {len(url_elements)} URLs in sitemap.")  
                else:  
                    logging.warning("Sitemap contains no URL entries.")  
                for url_elem in url_elements:  
                    loc = url_elem.find('ns:loc', namespaces=namespace).text  
                    urls.append(loc)  
            else:  
                logging.warning("Unrecognized sitemap format.")  
            return urls  
        except Exception as e:  
            logging.error(f"Error parsing sitemap: {e}")  
            return []  
  
    @staticmethod  
    def parse_sitemap_url(sitemap_url):  
        """  
        Fetch and parse the sitemap from a given URL.  
        """  
        headers = {"User-Agent": "Mozilla/5.0"}  
        try:  
            response = requests.get(sitemap_url, headers=headers, timeout=10)  
            if response.status_code == 200:  
                return Crawler.parse_sitemap(response.text)  
        except Exception as e:  
            logging.error(f"Error fetching sitemap from {sitemap_url}: {e}")  
        return []  
  
    async def scrape_sitemap_urls(self, urls):  
        """  
        Scrape full HTML content from the list of URLs provided by the sitemap.  
        """  
        logging.info(f"Starting to scrape {len(urls)} URLs from sitemap.")  
  
        all_data = []  
  
        if not urls:  
            logging.warning(f"No URLs found in sitemap for {self.base_url}")  
            return all_data  # Return empty data  
  
        for url in urls:  
            if len(self.visited_urls) >= self.max_pages:  
                logging.info(f"Reached max pages limit: {self.max_pages}")  
                break  
            if url in self.visited_urls:  
                continue  
            if not url.startswith(self.base_domain):  
                continue  
            try:  
                logging.info(f"Visiting URL from sitemap: {url}")  
                content, ocr_text = await self.scrape_url(url)  
                if content or ocr_text:  
                    logging.info(f"Content extracted from: {url}")  
                    all_data.append({"url": url, "html_content": content, "ocr_text": ocr_text})  
                    DataManager.append_to_json_file(  
                        f"logs/crawled_data_{self.parsed_base_url.netloc.replace('.', '_')}.json",  
                        {"url": url, "html_content": content, "ocr_text": ocr_text},  
                    )  
                else:  
                    logging.warning(f"No content extracted from: {url}")  
  
                self.visited_urls.add(url)  
                await asyncio.sleep(1)  # Delay to be polite to the server  
  
            except Exception as e:  
                logging.error(f"Error processing {url}: {e}")  
  
        visited_log_file = os.path.join("logs", f"visited_urls_{self.parsed_base_url.netloc.replace('.', '_')}.log")  
        with open(visited_log_file, "w", encoding="utf-8") as file:  
            file.write("\n".join(self.visited_urls))  
        logging.info(f"Visited URLs saved to: {visited_log_file}")  
  
        return all_data  
  
    async def crawl_website_recursive(self):  
        """  
        Recursively crawl a website and scrape full HTML content.  
        """  
        logging.info(f"Starting recursive crawl for {self.base_url}")  
        to_visit = [(self.base_url, 0)]  
        all_data = []  
  
        while to_visit and len(self.visited_urls) < self.max_pages:  
            current_url, depth = to_visit.pop(0)  
            if current_url in self.visited_urls or depth > self.max_depth:  
                continue  
  
            try:  
                logging.info(f"Visiting URL: {current_url}")  
                content, ocr_text = await self.scrape_url(current_url)  
                if content or ocr_text:  
                    logging.info(f"Content extracted from: {current_url}")  
                    all_data.append({"url": current_url, "html_content": content, "ocr_text": ocr_text})  
                    DataManager.append_to_json_file(  
                        f"logs/crawled_data_{self.parsed_base_url.netloc.replace('.', '_')}.json",  
                        {"url": current_url, "html_content": content, "ocr_text": ocr_text},  
                    )  
                else:  
                    logging.warning(f"No content extracted from: {current_url}")  
  
                self.visited_urls.add(current_url)  
  
                # Parse links for further crawling  
                soup = BeautifulSoup(content, 'html.parser')  
                if soup:  
                    for a_tag in soup.find_all('a', href=True):  
                        link = urljoin(self.base_url, a_tag['href'])  
                        if link not in self.visited_urls and link.startswith(self.base_domain):  
                            logging.info(f"Enqueuing subpage: {link}")  
                            to_visit.append((link, depth + 1))  
  
                await asyncio.sleep(1)  # Delay to be polite to the server  
  
            except Exception as e:  
                logging.error(f"Error processing {current_url}: {e}")  
  
        visited_log_file = os.path.join("logs", f"visited_urls_{self.parsed_base_url.netloc.replace('.', '_')}.log")  
        with open(visited_log_file, "w", encoding="utf-8") as file:  
            file.write("\n".join(self.visited_urls))  
        logging.info(f"Visited URLs saved to: {visited_log_file}")  
  
        return all_data  
  
    async def scrape_url(self, url):  
        """  
        Scrape content from a single URL.  
        """  
        if self.use_dynamic == "playwright":  
            content, ocr_text = await self.scraper.extract_dynamic_content_with_playwright_async(  
                url, self.screenshot_dir  
            )  
        else:  
            headers = {"User-Agent": "Mozilla/5.0"}  
            response = requests.get(url, headers=headers, timeout=10)  
            response.raise_for_status()  
            content = response.text  
            ocr_text = ""  
        return content, ocr_text  