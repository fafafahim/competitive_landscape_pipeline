import asyncio  
import logging  
import csv  
import time   
from logger_setup import LoggerSetup  
from company_processor import CompanyProcessor  
from data_manager import DataManager  
  
async def main():  
    # Initialize logging  
    LoggerSetup.setup_logging()  
  
    company_processor = CompanyProcessor()  
  
    # Read competitor_companies.csv and build competitor_data['companies'] and websites_dict  
    competitor_data = {'companies': []}  
    websites_dict = {}  
    try:  
        with open('competitor_companies.csv', 'r', encoding='utf-8') as csvfile:  
            reader = csv.DictReader(csvfile)  
            for row in reader:  
                company_name = row.get('name', '').strip()  
                website = row.get('website', '').strip()  
                if company_name:  
                    competitor_data['companies'].append({'name': company_name, 'website': website})  
                    if website:  
                        websites_dict[company_name] = website  
    except Exception as e:  
        logging.error(f"Error reading competitor_companies.csv: {e}")  
        return  
  
    total_companies = len(competitor_data['companies'])  
    logging.info(f"Total companies to process: {total_companies}")  
  
    # Start the total timer  
    total_start_time = time.time()  
  
    # Process each company  
    for idx, company in enumerate(competitor_data["companies"], start=1):  
        company_name = company.get("name", "").strip()  
        if not company_name:  
            logging.warning("A company entry is missing the 'name' key. Skipping...")  
            continue  
        company_name_normalized = company_name.lower()  
  
        # Start timer for this company  
        company_start_time = time.time()  
  
        existing_analysis = DataManager.load_company_analysis("logs/competitive_analysis.json", company_name)  
        if existing_analysis:  
            existing_inquiries = set(existing_analysis.get("inquiry_answers", {}).keys())  
            all_inquiries = set([inq['question'] for inq in company_processor.inquiries])  
            new_inquiries = all_inquiries - existing_inquiries  
            if not new_inquiries:  
                logging.info(f"Skipping {company_name}, inquiries are already up-to-date.")  
                continue  
            else:  
                logging.info(f"Processing new inquiries for {company_name}")  
                failed = await company_processor.process_company(  
                    company_name,  
                    company.get('website', '').strip(),  
                    websites_dict,  
                    existing_analysis=existing_analysis  
                )  
        else:  
            logging.info(f"Processing company {company_name} ({idx}/{total_companies}).")  
            failed = await company_processor.process_company(  
                company_name,  
                company.get('website', '').strip(),  
                websites_dict,  
                existing_analysis=None  
            )  
  
        # Calculate the time taken for this company  
        company_end_time = time.time()  
        company_elapsed_time = company_end_time - company_start_time  
        logging.info(f"Processed {company_name} ({idx}/{total_companies}) in {company_elapsed_time:.2f} seconds.")  
  
    # Calculate total elapsed time  
    total_end_time = time.time()  
    total_elapsed_time = total_end_time - total_start_time  
    logging.info(f"All companies processed in {total_elapsed_time:.2f} seconds.")  
  
if __name__ == "__main__":  
    asyncio.run(main())  