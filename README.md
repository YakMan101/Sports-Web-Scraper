# Sports Web Scraper

## Notes
- This is a recreation of an old project. The code is in process of being refactored and cleaned.
- Places leisure centre script is unfinished

## 📝 Project Overview
Sports Web Scraper is a simple collection of scripts to automate the search for activity bookings local to a specified location. This alleveiates the need to manually sift through leisure centre websites one by one.

## 🛠️ Prerequisites

- **Python (working = 3.12)** Installed
- **Google Chrome** Installed

## 📂 Setup
1. Clone the repository
```bash
git clone https://github.com/YakMan101/Sports-Web-Scraper.git
```

2. Create `.env` file containing the following:
```bash
POSTCODE=<uk_post_code_from_where_you_want_to_run_query>
ACTIVITY=<activity_to_serach_for>
EMAIL=<email_for_everyoneactive_login>
EA_PASS=<password_for_everyoneactive_login>
```

3. Create and activate virtual environment
- Linux/MacOS
```bash
python3 -m venv .venv
source .venv/bin/activate
```
- Windows PowerShell
```bash
python -m venv .venv
.venv\Scripts\activate
```

4. Run web scraper
```bash
python3 main.py
```