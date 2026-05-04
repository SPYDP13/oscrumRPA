# /Users/yves/Documents/personnel/brvm/OrangeScrumRpa/config.py

import os
from dotenv import load_dotenv

load_dotenv()  # Charge automatiquement le fichier .env

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
GITLAB_TOKEN    = os.getenv("GITLAB_TOKEN")
OSCRUM_USERNAME = os.getenv("OSCRUM_USERNAME")
OSCRUM_PASSWORD = os.getenv("OSCRUM_PASSWORD")
OSCRUM_PROJECT = os.getenv("OSCRUM_PROJECT")
