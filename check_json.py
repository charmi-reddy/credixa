import json
import os

path = r"backend\backend\artifacts\InvoiceFinancing.arc56.json"
if os.path.exists(path):
    with open(path, "r") as f:
        data = json.load(f)
    print(f"Keys in JSON: {list(data.keys())}")
    if "source" in data:
        print(f"Keys in source: {list(data['source'].keys())}")
    else:
        print("Key 'source' NOT found!")
else:
    print(f"File NOT found at {path}")
