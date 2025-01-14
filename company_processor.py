import os      
import time      
import logging      
import requests      
import json      
import asyncio      
from data_manager import DataManager      
from web_scraper import WebScraper      
from crawler import Crawler      
from openai import OpenAI
from dotenv import load_dotenv  
  
load_dotenv()  
  
class CompanyProcessor:      
    def __init__(self):      
        self.data_manager = DataManager()      
        self.web_scraper = WebScraper()      
        self.inquiries_file = "inquiries.json"      
        self.inquiries = DataManager.load_inquiries(self.inquiries_file)      
        # Load Google API key and Custom Search Engine ID from environment variables      
        self.google_api_key = os.getenv("GOOGLE_API_KEY")      
        self.google_cse_id = os.getenv("GOOGLE_CSE_ID")      
        # Load Azure OpenAI credentials    
        self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")    
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")    
        self.azure_deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME")    
        self.azure_api_version = os.getenv("AZURE_API_VERSION")    
        # Load Perplexity API key    
        self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
        # print(f"Perplexity API Key Loaded: {self.perplexity_api_key}")
  
    def extract_questions(self, key_descriptions, company_name):    
        """    
        Extract questions from the key_descriptions JSON structure and construct questions    
        by prepending 'For {company_name}, ' to each description.    
        """    
        questions = []    
  
        def process_node(node, prefix=""):    
            if isinstance(node, dict):    
                for key, value in node.items():    
                    process_node(value, prefix=f"{prefix}{key} -> " if prefix else f"{key} -> ")    
            elif isinstance(node, str):    
                # Construct the question    
                question = f"For {company_name}, {node}"    
                questions.append((prefix.rstrip(" -> "), question))    
  
        process_node(key_descriptions)    
        return questions    
  
    async def process_company(self, company_name, company_website, websites_dict, existing_analysis=None):      
        """      
        Process a single company: scrape data, clean it, perform analysis, and handle inquiries.      
        """      
        logging.info(f"Processing company: {company_name}")      
        failed_companies = {"website": False, "bing_news": False, "elion": False, "google_search": False}      
        competitive_analysis = None  # Ensure competitive_analysis is initialized      
  
        # Create directories for screenshots      
        screenshot_dir = os.path.join("screenshots", company_name.replace(' ', '_'))      
        os.makedirs(screenshot_dir, exist_ok=True)      
  
        if not existing_analysis:      
            try:      
                # Fetch or search for the company website      
                company_website = self.web_scraper.fetch_or_search_company_website(company_name, websites_dict)      
                if company_website == "Website not found.":      
                    logging.warning(f"Website not found for {company_name}.")      
                    failed_companies["website"] = True      
                    scraped_data = []      
                else:      
                    if not company_website.endswith('/'):      
                        company_website += '/'      
  
                    crawler = Crawler(      
                        base_url=company_website,      
                        max_pages=20,      
                        max_depth=2,      
                        use_dynamic="playwright",      
                        screenshot_dir=screenshot_dir,      
                    )      
  
                    # Fetch sitemap URLs      
                    sitemap_urls = crawler.fetch_sitemap_urls()      
                    if sitemap_urls:      
                        # Scrape content from the sitemap URLs      
                        scraped_data = await crawler.scrape_sitemap_urls(sitemap_urls)      
                        if not scraped_data:      
                            logging.warning(      
                                f"No data scraped from sitemap URLs for {company_name}. Falling back to recursive crawling.")      
                            # Fall back to recursive crawling      
                            scraped_data = await crawler.crawl_website_recursive()      
                    else:      
                        logging.warning(f"No sitemap URLs found for {company_name}. Falling back to recursive crawling.")      
                        # Fall back to recursive crawling      
                        scraped_data = await crawler.crawl_website_recursive()      
                    if not scraped_data:      
                        failed_companies["website"] = True      
  
                # Fetch Bing News articles and add them to the combined data      
                bing_news_data = self.fetch_bing_news(company_name)      
                if not bing_news_data:      
                    failed_companies["bing_news"] = True      
  
                # Extract data from Elion.Health      
                elion_data = await self.research_company_elion(company_name)      
                if isinstance(elion_data, list):      
                    elion_failed = False if elion_data else True      
                else:      
                    elion_failed = True      
                    elion_data = []      
                if elion_failed:      
                    failed_companies["elion"] = True      
  
                # Perform Google search and scrape results      
                google_search_data = await self.perform_google_search_and_scrape(company_name, company_website)      
                if not google_search_data:      
                    failed_companies["google_search"] = True      
  
                # Combine all data      
                combined_data = scraped_data + bing_news_data + elion_data + google_search_data      
  
                # Clean combined crawled data with LLM      
                cleaned_data_result = self.clean_data_with_azure_openai(company_name, combined_data)      
                cleaned_data = cleaned_data_result.get("data", [])      
  
                if not cleaned_data:    
                    # Handle the case of no cleaned data    
                    failed_companies["cleaned_data"] = True    
                    logging.warning(f"No cleaned data for {company_name}.")    
  

                # Proceed to process questions and append responses to cleaned_data    
                # Load key descriptions from key_descriptions_v6.json    
                key_descriptions_file = 'key_descriptions_v6.json'    
                key_descriptions = DataManager.load_json_file(key_descriptions_file)    
  
                if not key_descriptions:    
                    logging.error(f"Key descriptions file {key_descriptions_file} is empty or missing.")    
                    return    
  
                # Extract questions specific to the company    
                questions = self.extract_questions(key_descriptions, company_name)    
  
                # Query Perplexity API for each question and collect responses    
                responses = []    
                for key_path, question in questions:    
                    logging.info(f"Asking Perplexity API: {question}")    
                    answer = self.query_perplexity(question)    
                    # Append to cleaned_data format    
                    response_entry = {    
                        "url": f"Question: {question}",    
                        "cleaned_content": answer    
                    }    
                    responses.append(response_entry)    
  
                    # Wait between requests to avoid rate limiting    
                    time.sleep(2)    
  
                # Append responses to cleaned_data    
                cleaned_data.extend(responses)    
  
                # Now save the cleaned data (after appending responses)    
                DataManager.append_to_json_file(      
                    "logs/final_cleaned_data.json",      
                    {"company_name": company_name, "cleaned_data": cleaned_data}      
                )    
  
  
                # Generate competitive analysis if there's any cleaned data      
                if cleaned_data:      
                    competitive_analysis = self.generate_competitive_analysis(company_name, company_website, cleaned_data)      
                else:      
                    competitive_analysis = {      
                        "company_name": company_name,      
                        "company_website": company_website,      
                        "analysis": "No data available to generate analysis.",      
                        "cleaned_data": cleaned_data      
                    }      
                    logging.warning(f"No cleaned data available for {company_name} to generate competitive analysis.")      
  
            except Exception as e:      
                logging.error(f"An error occurred while processing {company_name}: {e}")      
                competitive_analysis = {      
                    "company_name": company_name,      
                    "company_website": company_website,      
                    "analysis": f"Error during processing: {e}",      
                    "cleaned_data": []      
                }      
        else:      
            # Load existing data      
            logging.info(f"Using existing analysis for {company_name}")      
            competitive_analysis = existing_analysis      
            cleaned_data = existing_analysis.get('cleaned_data', [])      
            company_website = competitive_analysis.get('company_website', company_website)      
  
        # Ensure competitive_analysis is not None before proceeding      
        if competitive_analysis is None:      
            competitive_analysis = {      
                "company_name": company_name,      
                "company_website": company_website,      
                "analysis": "No analysis available.",      
                "cleaned_data": []      
            }      
  
        # Process inquiries for the company      
        existing_inquiry_answers = competitive_analysis.get("inquiry_answers", {})      
        inquiry_answers = self.process_inquiries(company_name, cleaned_data, existing_inquiry_answers)      
  
        # Combine competitive_analysis and inquiry_answers      
        competitive_analysis["inquiry_answers"] = inquiry_answers      
  
        # Save the combined output to competitive_analysis.json      
        DataManager.update_json_file("logs/competitive_analysis.json", competitive_analysis, 'company_name')      
  
        return failed_companies      

    def query_perplexity(self, question):
        """Query the Perplexity API with the given question."""
        try:
            if not self.perplexity_api_key:
                logging.error("Perplexity API key is not set in the environment variables.")
                return "Perplexity API key not found."

            client = OpenAI(api_key=self.perplexity_api_key, base_url="https://api.perplexity.ai")

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are researching questions about a company. Your goal is to answer the question at hand as accurately as possible. "
                        "If no answer is available, return 'No answer available'. Always include relevant links to sources in your answers."
                    ),
                },
                {
                    "role": "user",
                    "content": question
                },
            ]

            # Make the API call
            response = client.chat.completions.create(
                model="llama-3.1-sonar-large-128k-online",
                messages=messages,
            )

            # Inspect the raw response for debugging
            logging.info(f"Raw API response: {response}")

            # Extract the assistant's reply
            if hasattr(response, "choices") and len(response.choices) > 0:
                answer = response.choices[0].message.content  
                return answer
            else:
                logging.warning("No choices available in the response.")
                return "No answer available."

        except Exception as e:
            logging.error(f"Perplexity API query failed for question: {question}. Error: {e}")
            return f"Error in fetching response from Perplexity API: {e}"

  
        except Exception as e:  
            logging.error(f"Perplexity API query failed for question: {question}. Error: {e}")  
            return f"Error in fetching response from Perplexity API: {e}"  
  
    def fetch_bing_news(self, company_name):    
        """    
        Fetch Bing News articles for the company.    
        """    
        logging.info(f"Fetching Bing News for {company_name}")    
        news_data = []    
        try:    
            api_key = os.getenv("BING_SEARCH_API_KEY")    
            if not api_key:    
                logging.error("BING_SEARCH_API_KEY is not set in environment variables.")    
                return []    
  
            endpoint = "https://api.bing.microsoft.com/v7.0/news/search"    
            headers = {"Ocp-Apim-Subscription-Key": api_key}    
            params = {    
                "q": f'"{company_name}"',    
                "count": 10,    
                "mkt": "en-US",    
                "originalImg": True,    
                "safeSearch": "Moderate",    
            }    
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)    
            response.raise_for_status()    
            search_results = response.json()    
  
            articles = search_results.get("value", [])    
            logging.info(f"Found {len(articles)} news articles for {company_name}.")    
  
            for article in articles:    
                url = article.get("url")    
                if url:    
                    content = self.fetch_full_article_content(url)    
                    news_data.append({    
                        "url": url,    
                        "html_content": content,    
                        "ocr_text": ""    
                    })    
        except Exception as e:    
            logging.error(f"Error fetching Bing News for {company_name}: {e}")    
  
        return news_data    
  
    def fetch_full_article_content(self, url):    
        """    
        Fetch the full content of an article from the given URL.    
        Retrieves the full HTML content.    
        """    
        try:    
            headers = {"User-Agent": "Mozilla/5.0"}    
            response = requests.get(url, headers=headers, timeout=10)    
            response.raise_for_status()    
            content = response.text    
            if not content:    
                logging.warning(f"No content extracted from: {url}")    
                return "Content could not be extracted."    
            return content    
        except Exception as e:    
            logging.error(f"Error fetching article content from {url}: {e}")    
            return "Content could not be extracted."    
  
    async def research_company_elion(self, company_name):    
        """    
        Use Elion.Health's sitemap to find the company's page and extract HTML content from it.    
        """    
        logging.info(f"Researching {company_name} on Elion.Health")    
        try:    
            sitemap_url = 'https://elion.health/sitemap-products.xml'    
            response = requests.get(sitemap_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)    
            response.raise_for_status()    
            urls = Crawler.parse_sitemap(response.text)    
  
            # Find the company's URL in the sitemap    
            company_url = None    
            for url in urls:    
                if company_name.lower().replace(' ', '-').replace('.', '') in url.lower():    
                    company_url = url    
                    break    
  
            if company_url:    
                logging.info(f"Found company page on Elion.Health: {company_url}")    
                # Crawl the company page and associated subpages    
                subpages = ['', '/features', '/reviews', '/customers', '/integrations']    
                all_urls = [company_url.rstrip('/') + subpage for subpage in subpages]    
                content = []    
  
                screenshot_dir = os.path.join("screenshots", "elion_health", company_name.replace(' ', '_'))    
                os.makedirs(screenshot_dir, exist_ok=True)    
  
                for url in all_urls:    
                    logging.info(f"Processing Elion.Health URL: {url}")    
                    page_content = await self.web_scraper.extract_dynamic_content_with_playwright_async(    
                        url, screenshot_dir)    
                    if page_content:    
                        content_data = {"url": url, "html_content": page_content[0], "ocr_text": page_content[1]}    
                        content.append(content_data)    
                        DataManager.append_to_json_file(    
                            f"logs/crawled_data_elion_{company_name.replace(' ', '_').lower()}.json", content_data)    
                    else:    
                        logging.warning(f"No content extracted from {url}")    
                return content if content else []    
            else:    
                logging.warning(f"Company {company_name} not found in Elion.Health sitemap.")    
                return []    
        except Exception as e:    
            logging.error(f"Error extracting data for {company_name} on Elion.Health: {e}")    
            return []    
  
    def clean_data_with_azure_openai(self, company_name, data, max_chunk_size=64000):    
        """    
        Clean the combined crawled data using Azure OpenAI.    
        """    
        try:    
            if not data:    
                logging.warning(f"No data to clean for {company_name}. Skipping cleanup.")    
                return {"company_name": company_name, "data": []}    
  
            # Split data into chunks based on max_chunk_size    
            chunks = []    
            current_chunk = []    
            current_chunk_size = 0    
  
            for entry in data:    
                entry_size = len(json.dumps(entry))    
                if current_chunk_size + entry_size > max_chunk_size:    
                    chunks.append(current_chunk)    
                    current_chunk = []    
                    current_chunk_size = 0    
                current_chunk.append(entry)    
                current_chunk_size += entry_size    
  
            # Add the last chunk if not empty    
            if current_chunk:    
                chunks.append(current_chunk)    
  
            logging.info(f"Data for {company_name} split into {len(chunks)} chunks for processing.")    
  
            cleaned_chunks = []    
  
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")    
            api_key = os.getenv("AZURE_OPENAI_API_KEY")    
            deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME_mini")    
            api_version = os.getenv("AZURE_API_VERSION")    
  
            for idx, chunk in enumerate(chunks):    
                prompt = (    
                    f"The following is crawled content from multiple pages of a website or sources about the company '{company_name}'. "    
                    "Clean up the data, remove duplicate information, and ensure the content is well-structured and concise. Only include data directly related to '{company_name}'.\n\n"    
                    f"{json.dumps(chunk, indent=2)}\n\n"    
                    "Return ONLY valid JSON and nothing else. The JSON should be an array of objects, "    
                    "each object must have two keys: 'url' and 'cleaned_content'. "    
                    "Do not include any commentary, explanations, markdown, or code fences. Just return JSON."    
                )    
  
                headers = {"Content-Type": "application/json", "api-key": api_key}    
                payload = {    
                    "messages": [    
                        {"role": "system", "content": "You are a helpful assistant that returns only the requested JSON output."},    
                        {"role": "user", "content": prompt}    
                    ],    
                    "temperature": 0    
                }    
  
                try:    
                    logging.info(f"Processing chunk {idx + 1}/{len(chunks)} for {company_name} using model: {deployment_name}...")    
                    response = requests.post(    
                        f"{azure_endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}",    
                        headers=headers,    
                        json=payload,    
                        timeout=60,    
                    )    
                    response.raise_for_status()    
                    result = response.json()["choices"][0]["message"]["content"].strip()    
  
                    # Attempt to fix code fences if any    
                    if "```" in result:    
                        result = result.replace("```json", "").replace("```", "").strip()    
  
                    if not (result.startswith("[") or result.startswith("{")):    
                        logging.error(f"The assistant returned output that does not look like JSON for chunk {idx + 1}/{len(chunks)}. Response: {result}")    
                        continue    
  
                    try:    
                        cleaned_data = json.loads(result)    
                        if not isinstance(cleaned_data, list):    
                            logging.error(f"Expected a JSON array but got: {type(cleaned_data)} for chunk {idx+1}/{len(chunks)}")    
                            continue    
                        cleaned_chunks.append(cleaned_data)    
                    except json.JSONDecodeError as e:    
                        logging.error(f"JSON decode error for chunk {idx + 1}/{len(chunks)}: {e} - Response was: {result}")    
                        continue    
                except Exception as e:    
                    logging.error(f"Error cleaning chunk {idx + 1}/{len(chunks)} for {company_name}: {e}")    
                    continue    
  
                # Wait 1 second between requests to avoid rate limiting    
                time.sleep(1)    
  
            # Combine cleaned chunks into a single structure    
            final_cleaned_data = []    
            for chunk in cleaned_chunks:    
                final_cleaned_data.extend(chunk)    
  
            return {"company_name": company_name, "data": final_cleaned_data}    
  
        except Exception as e:    
            logging.error(f"Error cleaning data with Azure OpenAI for {company_name}: {e}")    
            return {"company_name": company_name, "data": data}    
  
    def generate_competitive_analysis(self, company_name, company_website, cleaned_data, max_retries=3):    
        """    
        Generate competitive analysis by processing all keys in a single prompt.    
        Each key may have an associated description that is included in the prompt to guide the model.    
        """    
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")    
        api_key = os.getenv("AZURE_OPENAI_API_KEY")    
        deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME")    
        api_version = os.getenv("AZURE_API_VERSION")    
  
        # Load key descriptions from JSON file    
        key_descriptions = DataManager.load_json_file('key_descriptions_v6.json')    
  
        # List of keys to analyze (you can adjust this list as needed)    
        keys_to_analyze = list(key_descriptions.keys())    
  
        # Build the prompt    
        prompt = (    
            "You are a helpful assistant that returns ONLY valid JSON.\n"    
            "Do not include any code fences, triple backticks, or markdown formatting.\n"    
            "Do not include any explanations, just return the JSON directly.\n"    
            "Generate a competitive landscape analysis as a single JSON object with the following keys:\n\n"    
        )    
  
        # Add keys and their descriptions to the prompt    
        for key in keys_to_analyze:    
            key_description = key_descriptions.get(key, "")    
            prompt += f"Key: {key}\n"    
            if key_description:    
                prompt += f"Description: {key_description}\n"    
            prompt += "\n"    
  
        prompt += (    
            "Input data is provided below. Combine and summarize it into the JSON object.\n"    
            f"Company Name: {company_name}\n"    
            f"Company Website: {company_website}\n"    
            f"Cleaned Data:\n{json.dumps(cleaned_data, indent=2)}\n\n"    
            "Return the response in JSON format as:\n{\n"    
        )    
        for key in keys_to_analyze:    
            prompt += f'  "{key}": "value",\n'    
        prompt = prompt.rstrip(',\n') + "\n}\n"  # Remove the last comma and close the JSON    
  
        # Log the generated prompt    
        logging.info(f"Generated prompt for company '{company_name}':\n{prompt}")    
  
        for attempt in range(max_retries):    
            headers = {"Content-Type": "application/json", "api-key": api_key}    
            payload = {    
                "messages": [    
                    {"role": "system", "content": "You must return only valid JSON with no extra formatting."},    
                    {"role": "user", "content": prompt}    
                ],    
                "temperature": 0    
            }    
  
            try:    
                response = requests.post(    
                    f"{azure_endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}",    
                    headers=headers,    
                    json=payload,    
                    timeout=60,    
                )    
                response.raise_for_status()    
  
                result = response.json()["choices"][0]["message"]["content"].strip()    
  
                # Remove code fences if any    
                if "```" in result:    
                    result = result.replace("```json", "").replace("```", "").strip()    
  
                # Parse the JSON result    
                analysis = json.loads(result)    
                analysis['company_name'] = company_name    
                analysis['company_website'] = company_website    
                # analysis['cleaned_data'] = cleaned_data  # Include cleaned data if needed    
                return analysis  # Return the analysis if successful    
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:    
                logging.error(f"Error generating analysis for company '{company_name}': {e}")    
                time.sleep(2)    
  
        # If all retries fail, return an error message    
        return {    
            "company_name": company_name,    
            "company_website": company_website,    
            "analysis": f"Error generating analysis after {max_retries} retries.",    
            "cleaned_data": cleaned_data    
        }    
  
    def process_inquiries(self, company_name, cleaned_data, existing_inquiry_answers=None):    
        """    
        Process inquiries (questions) for the company using Azure OpenAI, cleaned data, and Bing web search results.    
        Only process inquiries that are not in existing_inquiry_answers.    
        """    
        logging.info(f"Processing inquiries for {company_name}")    
        answers = existing_inquiry_answers.copy() if existing_inquiry_answers else {}    
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")    
        api_key = os.getenv("AZURE_OPENAI_API_KEY")    
        deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME")    
        api_version = os.getenv("AZURE_API_VERSION")    
  
        if not all([api_key, azure_endpoint, deployment_name]):    
            logging.error("Azure OpenAI credentials are not set properly in the environment variables.")    
            return answers    
  
        for inquiry in self.inquiries:    
            question = inquiry.get("question")    
            if not question:    
                continue    
            if question in answers:    
                logging.info(f"Inquiry already answered: {question}")    
                continue    
            logging.info(f"Processing inquiry: {question}")    
  
            # Perform Bing web search for the question related to the company    
            search_query = f"{company_name} {question}"    
            web_search_results = self.web_scraper.search_bing_web(search_query)    
  
            # Combine cleaned data and web search results    
            combined_data = {    
                "cleaned_data": cleaned_data,    
                "web_search_results": web_search_results    
            }    
  
            prompt = (    
                f"You are a knowledgeable assistant. Based on the data provided, please answer the following question "    
                f"about \"{company_name}\":\n\n"    
                f"Question: {question}\n\n"    
                f"Data:\n{json.dumps(combined_data, indent=2)}\n\n"    
                "Please provide a concise and accurate answer."    
            )    
  
            headers = {"Content-Type": "application/json", "api-key": api_key}    
            payload = {    
                "messages": [    
                    {"role": "system", "content": "You are a helpful assistant."},    
                    {"role": "user", "content": prompt}    
                ],    
                "temperature": 0.5,    
                "max_tokens": 500    
            }    
  
            try:    
                response = requests.post(    
                    f"{azure_endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}",    
                    headers=headers,    
                    json=payload,    
                    timeout=60,    
                )    
                response.raise_for_status()    
                result = response.json()["choices"][0]["message"]["content"].strip()    
                answers[question] = result    
                logging.info(f"Answer received for inquiry: {question}")    
            except Exception as e:    
                logging.error(f"Error processing inquiry '{question}' for company '{company_name}': {e}")    
                answers[question] = f"Error: {e}"    
  
            # Wait between requests to avoid rate limiting    
            time.sleep(1)    
  
        return answers    
  
    def add_inquiry(self, question):    
        """    
        Add a new inquiry to the list and save it.    
        """    
        if not any(inquiry['question'] == question for inquiry in self.inquiries):    
            self.inquiries.append({"question": question})    
            DataManager.save_inquiries(self.inquiries_file, self.inquiries)    
            logging.info(f"Added new inquiry: {question}")    
        else:    
            logging.info(f"Inquiry already exists: {question}")    
  
    async def perform_google_search_and_scrape(self, company_name, company_website):    
        """    
        Perform a Google search of the company name, retrieve the top 10 non-company website results,    
        scrape the websites for content, and return the scraped data.    
        """    
        if not self.google_api_key or not self.google_cse_id:    
            logging.error("Google API key or Custom Search Engine ID (CX) not set in environment variables.")    
            return []    
  
        logging.info(f"Performing Google search for {company_name}")    
        try:    
            search_results = self.google_search_company(company_name)    
            if not search_results:    
                logging.warning(f"No Google search results for {company_name}.")    
                return []    
  
            # Filter out company website and sponsored results    
            company_domain = self.extract_domain(company_website)    
            filtered_results = []    
            for item in search_results:    
                item_domain = self.extract_domain(item.get('link', ''))    
                if company_domain and item_domain == company_domain:    
                    continue  # Skip company's own website    
                filtered_results.append(item)    
  
            # Limit to top 10 results    
            top_results = filtered_results[:10]    
  
            # Scrape content from each URL    
            scraped_data = []    
            for result in top_results:    
                url = result.get('link')    
                if url:    
                    content, ocr_text = await self.scrape_external_url(url)    
                    if content or ocr_text:    
                        logging.info(f"Content extracted from: {url}")    
                        scraped_data.append({"url": url, "html_content": content, "ocr_text": ocr_text})    
                        DataManager.append_to_json_file(    
                            f"logs/crawled_data_google_search_{company_name.replace(' ', '_').lower()}.json",    
                            {"url": url, "html_content": content, "ocr_text": ocr_text}    
                        )    
                    else:    
                        logging.warning(f"No content extracted from: {url}")    
                    # Be polite to servers    
                    await asyncio.sleep(1)    
            return scraped_data    
        except Exception as e:    
            logging.error(f"Error performing Google search and scraping for {company_name}: {e}")    
            return []    
  
    def google_search_company(self, company_name):    
        """    
        Use Google Custom Search API to search for the company name and return search results.    
        """    
        try:    
            endpoint = "https://www.googleapis.com/customsearch/v1"    
            params = {    
                "key": self.google_api_key,    
                "cx": self.google_cse_id,    
                "q": company_name,    
                "num": 10,    
            }    
            response = requests.get(endpoint, params=params, timeout=10)    
            response.raise_for_status()    
            search_results = response.json()    
            items = search_results.get('items', [])    
            logging.info(f"Retrieved {len(items)} search results from Google for {company_name}.")    
            return items    
        except Exception as e:    
            logging.error(f"Error fetching Google search results for {company_name}: {e}")    
            return []    
  
    def extract_domain(self, url):    
        """    
        Extract the domain from a URL.    
        """    
        if not url:    
            return None    
        parsed_url = requests.utils.urlparse(url)    
        return parsed_url.netloc.lower()    
  
    async def scrape_external_url(self, url):    
        """    
        Scrape content from an external URL using Playwright.    
        """    
        # Use a separate screenshot directory for external URLs    
        screenshot_dir = os.path.join("screenshots", "google_search_results")    
        os.makedirs(screenshot_dir, exist_ok=True)    
        content, ocr_text = await self.web_scraper.extract_dynamic_content_with_playwright_async(    
            url, screenshot_dir    
        )    
        return content, ocr_text    