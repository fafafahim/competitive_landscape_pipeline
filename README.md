# Competitive Landscape Pipeline

### Step 1: Set Up Environment Variables
1. Create a `.env` file.
2. Add your keys. Use `env.txt` as a reference.

---

### Step 2: Install Requirements
1. Activate your virtual environment (if applicable):

   **macOS/Linux**:
   ```bash
   source .venv/bin/activate
   ```

   **Windows**:
   ```cmd
   .venv\Scripts\activate
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

---

### Step 3: Install Playwright
1. Install Playwright:
   ```bash
   pip install playwright
   ```

2. Install the necessary browser binaries:
   ```bash
   python -m playwright install
   ```

---

### Step 4: Add Potential Competitors
1. Modify the `competitor_companies.csv` file.  
   Structure:
   ```csv
   name,website
   ```

---

### Step 5: Customize Search Questions
1. Adjust the questions in `key_descriptions_v6.json` to align with your company's objectives.
2. If additional questions arise, include them for analysis across all competitors in `inquiries.json` and rerun the pipeline. It will skip companies and inquiries that have already been processed.

---

### Step 6: Run the Script
1. Execute the main script:
   ```bash
   python main.py
   ```

2. Output file: `logs/final_cleaned_data.json`

