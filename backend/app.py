from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, Union
import base64
import os
import traceback

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
    os.getenv("ALGORAND_ALGOD_TOKEN", ""),
    os.getenv("ALGORAND_ALGOD_ADDRESS", "https://testnet-api.algonode.cloud"),
)

def load_contract_spec():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # The file is at backend/artifacts/... relative to app.py
    artifact_path = os.path.join(base_dir, "backend", "artifacts", "InvoiceFinancing.arc56.json")
    
    print(f"Loading contract spec from: {artifact_path}")
    
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
    raise HTTPException(
        status_code=410,
        detail="Disabled: backend signing is not allowed. Use wallet-based ASA endpoints only.",
    )

class InvoiceCreateReq(BaseModel):
    amount: int  # microAlgos


class DbInvoiceCreateReq(BaseModel):
    amount: float
    owner: str
    status: str = "pending"


class InvoiceStatusUpdateReq(BaseModel):
    status: str


class AsaCreatePrepareReq(BaseModel):
    amount: int | None = None
    supplier: str | None = None
    supplier_address: str | None = None
    invoice_id: int | None = None


class AsaCreateSubmitReq(BaseModel):
    invoice_id: int | None = None
    signed_txn: str


class InvoiceFundingPrepareReq(BaseModel):
    investor: str


class InvoiceFundingSubmitReq(BaseModel):
    investor: str
    signed_txns: list[str]

@app.post("/create_invoice")
def create_invoice(req: InvoiceCreateReq):
    raise HTTPException(
        status_code=410,
        detail="Disabled: backend signing is not allowed. Use /asa/invoices/create/prepare and wallet signing.",
    )

@app.post("/request_financing")
def request_financing():
    raise HTTPException(
        status_code=410,
        detail="Disabled: backend signing is not allowed. Use ASA wallet flow.",
    )

@app.post("/fund_invoice")
def fund_invoice():
    raise HTTPException(
        status_code=410,
        detail="Disabled: backend signing is not allowed. Use /asa/invoices/{id}/fund/prepare and wallet signing.",
    )

@app.get("/status")
def get_status():
    try:
        node_status = algod.status()
        return {
            "status": "ok",
            "network": "testnet",
            "algod_address": os.getenv("ALGORAND_ALGOD_ADDRESS", "https://testnet-api.algonode.cloud"),
            "last_round": node_status.get("last-round"),
            "time_since_last_round": node_status.get("time-since-last-round"),
        }
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
        supplier = (req.supplier or req.supplier_address or "").strip()
        if not supplier:
            raise HTTPException(status_code=400, detail="supplier (or supplier_address) is required")

        amount = int(req.amount or 1_000_000)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be > 0")

        invoice = create_invoice_record(
            amount=amount,
            owner=supplier,
            status="CREATED",
        )
        invoice_id = int(invoice["id"])

        sp = _suggested_params()
        asa_create_txn = transaction.AssetConfigTxn(
            sender=supplier,
            sp=sp,
            total=1,
            default_frozen=False,
            unit_name="INV",
            asset_name=f"Invoice_{invoice_id}",
            manager=supplier,
            reserve=supplier,
            freeze=supplier,
            clawback=supplier,
            decimals=0,
        )

        unsigned_txn = _to_base64_txn(asa_create_txn)
        return {
            "message": "Unsigned ASA creation transaction prepared",
            "invoice": invoice,
            "unsigned_txn": unsigned_txn,
            "txn": unsigned_txn,
            "tx_id": asa_create_txn.get_txid(),
            "asset_name": f"Invoice_{invoice_id}",
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/asa/invoices/create/submit")
def asa_create_invoice_submit(req: AsaCreateSubmitReq):
    try:
        raw_signed_txn = _from_base64_signed_txn(_normalize_signed_txn(req.signed_txn))
        tx_id = algod.send_raw_transaction(raw_signed_txn)
        confirmation = transaction.wait_for_confirmation(algod, tx_id, 4)
        asa_id = int(confirmation.get("asset-index", 0))
        if not asa_id:
            raise RuntimeError("ASA creation succeeded but asset-index missing in confirmation")

        if req.invoice_id is not None:
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

        return {
            "message": "Invoice Created on Testnet!",
            "txid": tx_id,
            "tx_id": tx_id,
            "asa_id": asa_id,
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
        tx_id = algod.send_raw_transaction(grouped_blob)
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
