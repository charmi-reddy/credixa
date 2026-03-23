from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, Union
import base64
import os
import sys
import traceback

import algokit_utils
from algokit_utils import AlgorandClient
from algokit_utils.applications import Arc56Contract
from algosdk import encoding
from algosdk import transaction
from algosdk.v2client.algod import AlgodClient
from .db import (
    get_app_state,
    update_app_state,
    test_supabase_connection,
    create_invoice_record,
    fetch_all_invoices,
    update_invoice_status_record,
    insert_sample_invoice,
    fetch_invoice_by_id,
    update_invoice_asa_record,
    update_invoice_funded_record,
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
algod = AlgodClient(
    os.getenv("ALGORAND_ALGOD_TOKEN", "a" * 64),
    os.getenv("ALGORAND_ALGOD_ADDRESS", "http://localhost:4001"),
)

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


class AsaCreatePrepareReq(BaseModel):
    amount: int
    supplier: str


class AsaCreateSubmitReq(BaseModel):
    invoice_id: int
    signed_txn: str


class InvoiceFundingPrepareReq(BaseModel):
    investor: str


class InvoiceFundingSubmitReq(BaseModel):
    investor: str
    signed_txns: list[str]

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
        amount_micro_algo = int(gs.get("amount").value) if "amount" in gs else 0
        if amount_micro_algo <= 0:
            raise Exception("Invalid invoice amount in global state")
        
        # Create payment txn
        payment = algorand.create_transaction.payment(
            algokit_utils.PaymentParams(
                sender=investor.address,
                receiver=state.supplier_addr,
                amount=algokit_utils.AlgoAmount.from_micro_algo(amount_micro_algo)
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


def _suggested_params() -> transaction.SuggestedParams:
    return algod.suggested_params()


def _to_base64_txn(txn: Any) -> str:
    return encoding.msgpack_encode(txn)


def _from_base64_signed_txn(signed_txn_b64: str) -> bytes:
    try:
        return base64.b64decode(signed_txn_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid signed transaction base64: {e}")


def _normalize_signed_txn(signed_txn_b64: str) -> str:
    candidate = (signed_txn_b64 or "").strip()
    if not candidate:
        raise HTTPException(status_code=400, detail="Signed transaction is empty")
    try:
        base64.b64decode(candidate)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid signed transaction base64: {e}")
    return candidate


def _account_holds_asset(address: str, asa_id: int) -> bool:
    account_info = algod.account_info(address)
    for asset in account_info.get("assets", []):
        if asset.get("asset-id") == asa_id and int(asset.get("amount", 0)) > 0:
            return True
    return False


def _validate_atomic_funding_group(
    signed_txn_b64_list: list[str],
    investor: str,
    supplier: str,
    amount: int,
    asa_id: int,
) -> tuple[str, str]:
    try:
        stx1 = encoding.msgpack_decode(signed_txn_b64_list[0])
        stx2 = encoding.msgpack_decode(signed_txn_b64_list[1])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to decode signed group transactions: {e}")

    tx1 = stx1.transaction
    tx2 = stx2.transaction

    if tx1.type != "pay":
        raise HTTPException(status_code=400, detail="Transaction 1 must be PaymentTxn")
    if tx2.type != "axfer":
        raise HTTPException(status_code=400, detail="Transaction 2 must be AssetTransferTxn")

    if tx1.sender != investor or tx1.receiver != supplier:
        raise HTTPException(status_code=400, detail="PaymentTxn direction must be investor -> supplier")
    if int(tx1.amt) != int(amount):
        raise HTTPException(status_code=400, detail="PaymentTxn amount must match invoice amount")

    if tx2.sender != supplier or tx2.receiver != investor:
        raise HTTPException(status_code=400, detail="AssetTransferTxn direction must be supplier -> investor")
    if int(tx2.index) != int(asa_id) or int(tx2.amount) != 1:
        raise HTTPException(status_code=400, detail="AssetTransferTxn must transfer exactly 1 unit of the invoice ASA")

    if tx1.group is None or tx2.group is None:
        raise HTTPException(status_code=400, detail="Both transactions must include a group id")
    if tx1.group != tx2.group:
        raise HTTPException(status_code=400, detail="Transactions must share the same group id")

    return tx1.get_txid(), tx2.get_txid()


@app.post("/asa/invoices/create/prepare")
def asa_create_invoice_prepare(req: AsaCreatePrepareReq):
    try:
        invoice = create_invoice_record(
            amount=req.amount,
            owner=req.supplier,
            status="CREATED",
        )
        invoice_id = int(invoice["id"])

        sp = _suggested_params()
        asa_create_txn = transaction.AssetConfigTxn(
            sender=req.supplier,
            sp=sp,
            total=1,
            default_frozen=False,
            unit_name="INV",
            asset_name=f"Invoice_{invoice_id}",
            manager=req.supplier,
            reserve=req.supplier,
            freeze=req.supplier,
            clawback=req.supplier,
            decimals=0,
        )

        return {
            "message": "Unsigned ASA creation transaction prepared",
            "invoice": invoice,
            "unsigned_txn": _to_base64_txn(asa_create_txn),
            "tx_id": asa_create_txn.get_txid(),
            "asset_name": f"Invoice_{invoice_id}",
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/asa/invoices/create/submit")
def asa_create_invoice_submit(req: AsaCreateSubmitReq):
    try:
        tx_id = algod.send_raw_transaction(_normalize_signed_txn(req.signed_txn))
        confirmation = transaction.wait_for_confirmation(algod, tx_id, 4)
        asa_id = int(confirmation.get("asset-index", 0))
        if not asa_id:
            raise RuntimeError("ASA creation succeeded but asset-index missing in confirmation")

        invoice = fetch_invoice_by_id(req.invoice_id)
        supplier = invoice.get("owner", "")
        if not supplier:
            raise RuntimeError("Invoice owner is missing; cannot verify ASA ownership")

        if not _account_holds_asset(supplier, asa_id):
            raise RuntimeError("Supplier does not hold the newly created ASA")

        updated = update_invoice_asa_record(invoice_id=req.invoice_id, asa_id=asa_id, status="TOKENIZED")
        return {
            "message": "Invoice tokenized successfully",
            "tx_id": tx_id,
            "asa_id": asa_id,
            "owner_verified": True,
            "invoice": updated,
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/asa/invoices/{invoice_id}")
def get_asa_invoice(invoice_id: Union[int, str]):
    try:
        return fetch_invoice_by_id(invoice_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/asa/invoices/{invoice_id}/fund/prepare")
def asa_prepare_funding(invoice_id: Union[int, str], req: InvoiceFundingPrepareReq):
    try:
        invoice = fetch_invoice_by_id(invoice_id)
        asa_id = int(invoice.get("asa_id") or 0)
        if asa_id <= 0:
            raise RuntimeError("Invoice is not tokenized yet (missing asa_id)")

        supplier = invoice["owner"]
        if not _account_holds_asset(supplier, asa_id):
            raise RuntimeError("Current invoice owner does not hold the ASA")

        amount = int(float(invoice["amount"]))
        if amount <= 0:
            raise RuntimeError("Invalid invoice amount")

        sp = _suggested_params()
        payment_txn = transaction.PaymentTxn(
            sender=req.investor,
            sp=sp,
            receiver=supplier,
            amt=amount,
        )
        asa_transfer_txn = transaction.AssetTransferTxn(
            sender=supplier,
            sp=sp,
            receiver=req.investor,
            amt=1,
            index=asa_id,
        )

        transaction.assign_group_id([payment_txn, asa_transfer_txn])

        return {
            "message": "Unsigned atomic funding group prepared",
            "invoice_id": invoice_id,
            "asa_id": asa_id,
            "group_id": base64.b64encode(payment_txn.group).decode("utf-8") if payment_txn.group else None,
            "unsigned_group_txns": [
                _to_base64_txn(payment_txn),
                _to_base64_txn(asa_transfer_txn),
            ],
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/asa/invoices/{invoice_id}/fund/submit")
def asa_submit_funding(invoice_id: Union[int, str], req: InvoiceFundingSubmitReq):
    try:
        if len(req.signed_txns) != 2:
            raise HTTPException(status_code=400, detail="signed_txns must contain exactly 2 signed transactions")

        invoice = fetch_invoice_by_id(invoice_id)
        asa_id = int(invoice.get("asa_id") or 0)
        if asa_id <= 0:
            raise RuntimeError("Invoice is not tokenized yet (missing asa_id)")

        supplier = invoice.get("owner", "")
        if not supplier:
            raise RuntimeError("Invoice owner is missing")

        amount = int(float(invoice.get("amount") or 0))
        if amount <= 0:
            raise RuntimeError("Invalid invoice amount")

        raw_signed_b64 = [_normalize_signed_txn(stxn) for stxn in req.signed_txns]
        pay_txid, axfer_txid = _validate_atomic_funding_group(
            signed_txn_b64_list=raw_signed_b64,
            investor=req.investor,
            supplier=supplier,
            amount=amount,
            asa_id=asa_id,
        )

        grouped_blob = b"".join(base64.b64decode(stxn) for stxn in raw_signed_b64)
        grouped_blob_b64 = base64.b64encode(grouped_blob).decode("utf-8")
        tx_id = algod.send_raw_transaction(grouped_blob_b64)
        transaction.wait_for_confirmation(algod, tx_id, 4)

        if not _account_holds_asset(req.investor, asa_id):
            raise RuntimeError("Funding transaction confirmed but investor does not hold the ASA")

        updated = update_invoice_funded_record(invoice_id=invoice_id, owner=req.investor, algo_tx_id=tx_id)
        return {
            "message": "Invoice funding completed atomically",
            "tx_id": tx_id,
            "payment_tx_id": pay_txid,
            "asset_transfer_tx_id": axfer_txid,
            "invoice": updated,
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/asa/invoices/{invoice_id}/verify")
def verify_invoice_owner(invoice_id: Union[int, str]):
    try:
        invoice = fetch_invoice_by_id(invoice_id)
        asa_id = int(invoice.get("asa_id") or 0)
        owner = invoice.get("owner", "")
        if asa_id <= 0:
            return {
                "invoice": invoice,
                "verified": False,
                "reason": "Invoice has no ASA",
            }

        holds = _account_holds_asset(owner, asa_id)
        return {
            "invoice": invoice,
            "verified": holds,
            "on_chain_owner": owner if holds else "mismatch",
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
