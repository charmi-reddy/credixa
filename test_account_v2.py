import json
import os
import algokit_utils
from algosdk.v2client.algod import AlgodClient
import traceback

algod_client = AlgodClient("a" * 64, "http://localhost:4001")

try:
    print("Attempting to get account 'supplier'...")
    acc = algokit_utils.get_account(algod_client, "supplier")
    print(f"Success: {acc.address}")
except Exception as e:
    print("FAILED:")
    traceback.print_exc()
