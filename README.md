# Sports Web Scraper

## 📝 Project Overview
Sports Web Scraper is a simple collection of scripts to automate the search for activity bookings local to a specified location. This alleveiates the need to manually sift through leisure centre websites one by one.

## 🛠️ Prerequisites

-**Python** Installed

## 📂 Setup
1. Create `.env` file containing the following:
```bash
POSTCODE=<uk_post_code_from_where_you_want_to_run_query>
ACTIVITY=<activity_to_serach_for>
EMAIL=<email_for_everyoneactive_login>
EA_PASS=<password_for_everyoneactive_login>
```

2. Create virtual environment
```bash
python3 -m venv .venv
```
3. Activate virtual environment 
- Windows PowerShell
```bash
.venv\Scripts\activate
```
- Linux/MacOS
```bash
source .venv/bin/activate
```

4. Run web scraper
```bash
python3 main.py
```