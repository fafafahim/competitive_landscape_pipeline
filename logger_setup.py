import os  
import logging  
from datetime import datetime  
  
class LoggerSetup:  
    @staticmethod  
    def setup_logging(log_dir="logs"):  
        """  
        Set up logging to track visited URLs and enqueued subpages.  
        """  
        os.makedirs(log_dir, exist_ok=True)  
        log_file = os.path.join(  
            log_dir, f"process_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"  
        )  
        logging.basicConfig(  
            level=logging.INFO,  # Change to logging.DEBUG for more detailed output  
            format="%(asctime)s [%(levelname)s] %(message)s",  
            handlers=[  
                logging.FileHandler(log_file, mode="w"),  
                logging.StreamHandler(),  
            ],  
        )  
        logging.info(f"Logging initialized. Logs will be saved to {log_file}")  