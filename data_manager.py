import os  
import json  
import logging  
  
class DataManager:  
    @staticmethod  
    def load_json_file(filename):  
        """  
        Load data from a JSON file or return an empty structure if the file doesn't exist.  
        """  
        if os.path.exists(filename):  
            with open(filename, "r", encoding="utf-8") as file:  
                try:  
                    return json.load(file)  
                except json.JSONDecodeError as e:  
                    logging.error(f"Error decoding JSON from {filename}: {e}")  
                    return {}  
        return {}  
  
    @staticmethod  
    def save_json_file(filename, data):  
        """  
        Save data to a JSON file.  
        """  
        with open(filename, "w", encoding="utf-8") as file:  
            json.dump(data, file, indent=4)  
        logging.info(f"Data saved to {filename}")  
  
    @staticmethod  
    def append_to_json_file(filename, entry):  
        """  
        Append an entry to a JSON file, creating the file if it doesn't exist.  
        """  
        existing_data = []  
        if os.path.exists(filename):  
            with open(filename, "r", encoding="utf-8") as file:  
                try:  
                    existing_data = json.load(file)  
                except json.JSONDecodeError as e:  
                    logging.error(f"Error decoding JSON from {filename}: {e}")  
        else:  
            logging.info(f"File {filename} does not exist. It will be created.")  
  
        existing_data.append(entry)  
  
        with open(filename, "w", encoding="utf-8") as file:  
            json.dump(existing_data, file, indent=4)  
        logging.info(f"Appended data to {filename}")  
  
    @staticmethod  
    def load_processed_companies(output_filename):  
        """  
        Load the names of companies that have already been processed from the output file.  
        """  
        if os.path.exists(output_filename):  
            with open(output_filename, "r", encoding="utf-8") as file:  
                try:  
                    data = json.load(file)  
                    if isinstance(data, list):  
                        return {item["company_name"].lower().strip() for item in data if  
                                "company_name" in item}  
                except json.JSONDecodeError as e:  
                    logging.error(f"Error decoding JSON from {output_filename}: {e}")  
        return set()  
  
    @staticmethod  
    def load_inquiries(filename):  
        """  
        Load the list of inquiries from a JSON file.  
        """  
        if os.path.exists(filename):  
            with open(filename, "r", encoding="utf-8") as file:  
                try:  
                    return json.load(file)  
                except json.JSONDecodeError as e:  
                    logging.error(f"Error decoding JSON from {filename}: {e}")  
        else:  
            logging.info(f"Inquiries file {filename} not found. Starting with an empty list.")  
        return []  
  
    @staticmethod  
    def save_inquiries(filename, inquiries):  
        """  
        Save the list of inquiries to a JSON file.  
        """  
        with open(filename, "w", encoding="utf-8") as file:  
            json.dump(inquiries, file, indent=4)  
        logging.info(f"Inquiries saved to {filename}")  
  
    @staticmethod  
    def load_company_analysis(filename, company_name):  
        """  
        Load the analysis for a specific company from a JSON file.  
        """  
        if os.path.exists(filename):  
            with open(filename, "r", encoding="utf-8") as file:  
                try:  
                    data = json.load(file)  
                    for item in data:  
                        if item.get('company_name', '').lower().strip() == company_name.lower():  
                            return item  
                except json.JSONDecodeError as e:  
                    logging.error(f"Error decoding JSON from {filename}: {e}")  
        return None  
  
    @staticmethod  
    def update_json_file(filename, updated_entry, key_field='company_name'):  
        """  
        Update an existing entry in a JSON file, or append it if it doesn't exist.  
        """  
        existing_data = []  
        if os.path.exists(filename):  
            with open(filename, "r", encoding="utf-8") as file:  
                try:  
                    existing_data = json.load(file)  
                except json.JSONDecodeError as e:  
                    logging.error(f"Error decoding JSON from {filename}: {e}")  
                    existing_data = []  
  
        updated = False  
        for idx, entry in enumerate(existing_data):  
            if entry.get(key_field, '').lower().strip() == updated_entry.get(key_field, '').lower().strip():  
                existing_data[idx] = updated_entry  
                updated = True  
                break  
        if not updated:  
            existing_data.append(updated_entry)  
        with open(filename, "w", encoding="utf-8") as file:  
            json.dump(existing_data, file, indent=4)  
        logging.info(f"Updated data in {filename}")  