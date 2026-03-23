from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Union
import json
import os
import sys
import traceback

import algokit_utils
from algokit_utils import AlgorandClient
from algokit_utils.applications import Arc56Contract
from .db import (
    get_app_state,
    update_app_state,
    test_supabase_connection,
    create_invoice_record,
    fetch_all_invoices,
    update_invoice_status_record,
    insert_sample_invoice,
    fetch_invoice_by_id,
)

app = FastAPI()

runtime_app_state = {
    "app_id": 0,
    "supplier_addr": "",
    "investor_addr": "",
}

# Ensure static dir exists
os.makedirs("backend/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# State to hold app ID of the deployed contract
class AppState:
    @property
    def app_id(self) -> int:
        persisted = get_app_state()
        return persisted.get("app_id", 0) or runtime_app_state["app_id"]
    
    @property
    def supplier_addr(self) -> str:
        persisted = get_app_state()
        return persisted.get("supplier_addr", "") or runtime_app_state["supplier_addr"]
    
    @property
    def investor_addr(self) -> str:
        persisted = get_app_state()
        return persisted.get("investor_addr", "") or runtime_app_state["investor_addr"]

state = AppState()

# Algorand Client
algorand = AlgorandClient.default_localnet()

def get_signer_account(name: str):
    print(f"Getting account for: {name}")
    sys.stdout.flush()
    try:
        acc = algorand.account.from_kmd(name)
        print(f"Got account: {acc.address}")
        sys.stdout.flush()
        return acc
    except Exception as e:
        print(f"Error getting account {name}: {e}")
        sys.stdout.flush()
        raise

def load_contract_spec():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # The file is at backend/artifacts/... relative to app.py
    artifact_path = os.path.join(base_dir, "backend", "artifacts", "InvoiceFinancing.arc56.json")
    
    print(f"Loading contract spec from: {artifact_path}")
    sys.stdout.flush()
    
    if not os.path.exists(artifact_path):
        # Fallback if base_dir is already inside backend
        alt_path = os.path.join(base_dir, "artifacts", "InvoiceFinancing.arc56.json")
        if os.path.exists(alt_path):
            artifact_path = alt_path
        else:
            raise Exception(f"Artifact not found at {artifact_path} or {alt_path}")

    with open(artifact_path, "r") as f:
        content = f.read()
    
    return Arc56Contract.from_json(content)

@app.get("/")
def read_root():
    return FileResponse("backend/static/index.html")

@app.post("/deploy")
def deploy_contract():
    try:
        supplier = get_signer_account("supplier")
        
        investor = get_signer_account("investor")

        app_spec = load_contract_spec()
            
        # Deploy using AppFactory
        factory = algorand.client.get_app_factory(
            app_spec=app_spec,
            default_sender=supplier.address
        )
        
        # In Algokit 4.x, factory.deploy() returns a tuple: (AppClient, AppFactoryDeployResult)
        _, response = factory.deploy()
        
        # Persist to Supabase
        update_app_state(
            app_id=response.app.app_id,
            supplier_addr=supplier.address,
            investor_addr=investor.address
        )

        runtime_app_state["app_id"] = response.app.app_id
        runtime_app_state["supplier_addr"] = supplier.address
        runtime_app_state["investor_addr"] = investor.address
        
        return {"message": "Contract deployed", "app_id": response.app.app_id, "supplier": supplier.address, "investor": investor.address}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class InvoiceCreateReq(BaseModel):
    amount: int  # microAlgos


class DbInvoiceCreateReq(BaseModel):
    amount: float
    owner: str
    status: str = "pending"


class InvoiceStatusUpdateReq(BaseModel):
    status: str

@app.post("/create_invoice")
def create_invoice(req: InvoiceCreateReq):
    try:
        if not state.app_id:
            raise Exception("Contract not deployed")

        supplier = get_signer_account("supplier")
        app_spec = load_contract_spec()
            
        app_client = algorand.client.get_app_client_by_id(
            app_spec=app_spec,
            app_id=state.app_id,
            default_sender=supplier.address
        )
        
        app_client.send.call(algokit_utils.AppCallMethodCallParams(
            method="create_invoice",
            sender=supplier.address,
            app_id=state.app_id,
            args=[req.amount]
        ))
        return {"message": "Invoice created successfully"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/request_financing")
def request_financing():
    try:
        if not state.app_id:
            raise Exception("Contract not deployed")

        supplier = get_signer_account("supplier")
        app_spec = load_contract_spec()
            
        app_client = algorand.client.get_app_client_by_id(
            app_spec=app_spec,
            app_id=state.app_id,
            default_sender=supplier.address
        )
        
        app_client.send.call(algokit_utils.AppCallMethodCallParams(
            method="request_financing",
            sender=supplier.address,
            app_id=state.app_id,
        ))
        return {"message": "Financing requested successfully"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fund_invoice")
def fund_invoice():
    try:
        if not state.app_id:
            raise Exception("Contract not deployed")

        investor = get_signer_account("investor")
        app_spec = load_contract_spec()
            
        app_client = algorand.client.get_app_client_by_id(
            app_spec=app_spec,
            app_id=state.app_id,
            default_sender=investor.address
        )
        
        # Read state to get the amount
        gs = app_client.get_global_state()
        amount = gs.get("amount").value if "amount" in gs else 0
        
        # Create payment txn
        payment = algorand.create_transaction.payment(
            algokit_utils.PaymentParams(
                sender=investor.address,
                receiver=state.supplier_addr,
                amount=amount
            )
        )
        
        app_client.send.call(algokit_utils.AppCallMethodCallParams(
            method="fund_invoice",
            sender=investor.address,
            app_id=state.app_id,
            args=[payment]
        ))
        return {"message": "Invoice funded atomically"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def get_status():
    if not state.app_id:
        return {"status": "Not Deployed"}
        
    try:
        app_spec = load_contract_spec()
        app_client = algorand.client.get_app_client_by_id(
            app_spec=app_spec,
            app_id=state.app_id
        )
        gs = app_client.get_global_state()
        # Convert AppState objects to their actual values for JSON serialization
        return {k: v.value for k, v in gs.items()}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


@app.get("/supabase/test")
def supabase_test():
    try:
        return test_supabase_connection()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/invoices")
def create_invoice_db(req: DbInvoiceCreateReq):
    try:
        return create_invoice_record(amount=req.amount, owner=req.owner, status=req.status)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/invoices")
def get_invoices_db():
    try:
        return {"invoices": fetch_all_invoices()}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/invoices/{invoice_id}/status")
def update_invoice_status(invoice_id: Union[int, str], req: InvoiceStatusUpdateReq):
    try:
        return update_invoice_status_record(invoice_id=invoice_id, status=req.status)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/invoices/seed-test")
def seed_and_fetch_invoice_test():
    try:
        inserted = insert_sample_invoice()
        fetched = fetch_invoice_by_id(inserted["id"])
        return {
            "message": "Sample invoice inserted and fetched successfully",
            "inserted": inserted,
            "fetched": fetched,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
