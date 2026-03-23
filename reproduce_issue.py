import json
import os
import sys
from algosdk.v2client.algod import AlgodClient
import algokit_utils

algod_client = AlgodClient("a" * 64, "http://localhost:4001")

def get_signer_account(name: str):
    print(f"Getting account for: {name}")
    return algokit_utils.get_account(algod_client, name)

def load_contract_spec():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"CWD: {os.getcwd()}")
    # Adjust path if needed for this script
    artifact_path = os.path.join(base_dir, "backend", "backend", "artifacts", "InvoiceFinancing.arc56.json")
    print(f"Loading from (abs): {os.path.abspath(artifact_path)}")
    if not os.path.exists(artifact_path):
        print("ERROR: File does not exist!")
        return None
    with open(artifact_path, "r") as f:
        # data = json.load(f) # We can just pass the string
        content = f.read()
    
    return algokit_utils.ApplicationSpecification.from_json(content)

try:
    print("Step 1: Getting supplier account")
    supplier = get_signer_account("supplier")
    print(f"Supplier: {supplier.address}")

    print("Step 2: Loading contract spec")
    app_spec = load_contract_spec()
    print("Contract spec loaded")

    print("Step 3: Creating ApplicationClient")
    typed_client = algokit_utils.ApplicationClient(
        algod_client=algod_client,
        app_spec=app_spec,
        signer=supplier
    )
    print("ApplicationClient created")

    print("Step 4: Deploying (create)")
    response = typed_client.create()
    print(f"Deployed! App ID: {response.app_id}")

except Exception as e:
    import traceback
    print("CRITICAL ERROR:")
    traceback.print_exc()
