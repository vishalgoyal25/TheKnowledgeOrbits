import os
import sys

import requests
from dotenv import load_dotenv

# Load env variables
load_dotenv(".env")

api_token = os.getenv("HF_API_TOKEN")
if not api_token:
    print("Error: HF_API_TOKEN not found in .env")
    sys.exit(1)

model = "all-MiniLM-L6-v2"
url = f"https://router.huggingface.co/hf-inference/models/sentence-transformers/{model}/pipeline/feature-extraction"
headers = {"Authorization": f"Bearer {api_token}"}
payload = {
    "inputs": ["Testing HuggingFace Inference API."],
    "options": {"wait_for_model": True},
}

print(f"Testing HF API token (first 4 chars): {api_token[:4]}...")
print(f"URL: {url}")
print("Sending request to HuggingFace Inference API...\n")

try:
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Success! Received embedding of length: {len(result[0])}")
    else:
        print(f"Failed! Response: {response.text}")
except Exception as e:
    print(f"Exception occurred: {e}")
