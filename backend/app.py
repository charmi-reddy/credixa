from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Union
import os
import traceback

from algosdk.v2client.algod import AlgodClient
from .wallet_config import (
    INVESTOR_STARTING_BALANCE,
    INVESTOR_WALLET,
    SUPPLIER_STARTING_BALANCE,
    SUPPLIER_WALLET,
)
from .db import (
    create_invoice_record,
    fetch_all_invoices,
    fetch_invoice_by_id,
    insert_sample_invoice,
    reset_all_invoices,
    test_supabase_connection,
    update_invoice_funded_record,
    update_invoice_status_record,
)

app = FastAPI()

os.makedirs("backend/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

algod = AlgodClient(
    os.getenv("ALGORAND_ALGOD_TOKEN", ""),
    os.getenv("ALGORAND_ALGOD_ADDRESS", "https://testnet-api.algonode.cloud"),
)

wallet_state = {
    "supplier": {
        "address": SUPPLIER_WALLET,
        "balance": SUPPLIER_STARTING_BALANCE,
    },
    "investor": {
        "address": INVESTOR_WALLET,
        "balance": INVESTOR_STARTING_BALANCE,
    },
}


class InvoiceCreateReq(BaseModel):
    amount: int


class DbInvoiceCreateReq(BaseModel):
    amount: float
    owner: str
    status: str = "pending"


class InvoiceStatusUpdateReq(BaseModel):
    status: str


class FundInvoiceReq(BaseModel):
    invoice_id: int | None = None


class BuyerAuthReq(BaseModel):
    buyer_id: str
    password: str


class RoleAuthReq(BaseModel):
    user_id: str
    password: str


buyer_accounts = {
    "1234": {
        "buyer_id": "1234",
        "password": "1234",
        "balance": 20000000,
    }
}

invoice_buyers: dict[str, str] = {}
invoice_financing: dict[str, dict] = {}

supplier_accounts = {
    "supplier": {
        "user_id": "supplier",
        "password": "1234",
    }
}

investor_accounts = {
    "investor": {
        "user_id": "investor",
        "password": "1234",
    }
}


def wallet_snapshot() -> dict:
    return {
        "supplier": wallet_state["supplier"]["address"],
        "investor": wallet_state["investor"]["address"],
        "connected": True,
        "balances": {
            "supplier": wallet_state["supplier"]["balance"],
            "investor": wallet_state["investor"]["balance"],
        },
    }


def enrich_invoice(invoice: dict) -> dict:
    enriched = dict(invoice)
    enriched["buyer_id"] = invoice_buyers.get(str(invoice.get("id")), "")
    financing = invoice_financing.get(str(invoice.get("id")), {})
    enriched["funded_amount"] = financing.get("funded_amount")
    enriched["face_amount"] = financing.get("face_amount", invoice.get("amount"))
    enriched["discount_rate"] = financing.get("discount_rate", 0.1)
    return enriched


def enrich_invoices(invoices: list[dict]) -> list[dict]:
    return [enrich_invoice(invoice) for invoice in invoices]


def serve_page(filename: str):
    return FileResponse(os.path.join("backend/static", filename))


@app.get("/")
def read_root():
    return serve_page("index.html")


@app.get("/supplier/login")
def supplier_login_page():
    return serve_page("supplier-login.html")


@app.get("/investor/login")
def investor_login_page():
    return serve_page("investor-login.html")


@app.get("/buyer/login")
def buyer_login_page():
    return serve_page("buyer-login.html")


@app.get("/supplier/dashboard")
def supplier_dashboard_page():
    return serve_page("supplier-dashboard.html")


@app.get("/investor/dashboard")
def investor_dashboard_page():
    return serve_page("investor-dashboard.html")


@app.get("/buyer/dashboard")
def buyer_dashboard_page():
    return serve_page("buyer-dashboard.html")


@app.get("/wallets")
def get_wallets():
    return wallet_snapshot()


@app.post("/auth/buyer/login")
def buyer_login(req: BuyerAuthReq):
    buyer_id = req.buyer_id.strip()
    password = req.password.strip()
    account = buyer_accounts.get(buyer_id)
    if not account or account["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid buyer ID or password")

    return {
        "role": "buyer",
        "buyer_id": buyer_id,
        "wallet": SUPPLIER_WALLET,
        "connected": True,
    }


@app.post("/auth/supplier/login")
def supplier_login(req: RoleAuthReq):
    user_id = req.user_id.strip()
    password = req.password.strip()
    account = supplier_accounts.get(user_id)
    if not account or account["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid supplier ID or password")

    return {
        "role": "supplier",
        "user_id": user_id,
        "wallet": SUPPLIER_WALLET,
        "connected": True,
    }


@app.post("/auth/investor/login")
def investor_login(req: RoleAuthReq):
    user_id = req.user_id.strip()
    password = req.password.strip()
    account = investor_accounts.get(user_id)
    if not account or account["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid investor ID or password")

    return {
        "role": "investor",
        "user_id": user_id,
        "wallet": INVESTOR_WALLET,
        "connected": True,
    }


@app.post("/auth/buyer/register")
def buyer_register(req: BuyerAuthReq):
    buyer_id = req.buyer_id.strip()
    password = req.password.strip()
    if not buyer_id or not password:
        raise HTTPException(status_code=400, detail="Buyer ID and password are required")
    if buyer_id in buyer_accounts:
        raise HTTPException(status_code=409, detail="Buyer ID already exists")

    buyer_accounts[buyer_id] = {
        "buyer_id": buyer_id,
        "password": password,
        "balance": 20000000,
    }
    return {
        "role": "buyer",
        "buyer_id": buyer_id,
        "wallet": SUPPLIER_WALLET,
        "connected": True,
    }


@app.post("/system/reset")
def reset_system():
    reset_all_invoices()
    invoice_buyers.clear()
    invoice_financing.clear()
    wallet_state["supplier"]["balance"] = SUPPLIER_STARTING_BALANCE
    wallet_state["investor"]["balance"] = INVESTOR_STARTING_BALANCE
    for buyer in buyer_accounts.values():
        buyer["balance"] = 20000000
    return {"message": "System reset complete"}


@app.get("/status")
def get_status():
    try:
        node_status = algod.status()
        return {
            "status": "ok",
            "mode": "predefined-wallets",
            "network": "testnet",
            "algod_address": os.getenv("ALGORAND_ALGOD_ADDRESS", "https://testnet-api.algonode.cloud"),
            "last_round": node_status.get("last-round"),
            "time_since_last_round": node_status.get("time-since-last-round"),
            "wallets": wallet_snapshot(),
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "degraded",
            "mode": "predefined-wallets",
            "error": str(e),
            "wallets": wallet_snapshot(),
        }


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
        return {"invoices": enrich_invoices(fetch_all_invoices())}
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
        invoice_buyers[str(inserted["id"])] = "1234"
        fetched = fetch_invoice_by_id(inserted["id"])
        return {
            "message": "Sample invoice inserted and fetched successfully",
            "inserted": enrich_invoice(inserted),
            "fetched": enrich_invoice(fetched),
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create_invoice")
def create_invoice(req: InvoiceCreateReq):
    try:
        invoice = create_invoice_record(
            amount=req.amount,
            owner=SUPPLIER_WALLET,
            status="CREATED",
        )
        invoice_buyers[str(invoice["id"])] = "1234"
        invoice_financing[str(invoice["id"])] = {
            "face_amount": req.amount,
            "discount_rate": 0.1,
            "funded_amount": None,
        }
        return enrich_invoice(invoice)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/invoices/create")
def create_invoice_for_supplier(req: InvoiceCreateReq, buyer_id: str):
    try:
        if req.amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be > 0")
        if buyer_id not in buyer_accounts:
            raise HTTPException(status_code=404, detail="Buyer account not found")

        invoice = create_invoice_record(
            amount=req.amount,
            owner=SUPPLIER_WALLET,
            status="CREATED",
        )
        invoice_buyers[str(invoice["id"])] = buyer_id
        invoice_financing[str(invoice["id"])] = {
            "face_amount": req.amount,
            "discount_rate": 0.1,
            "funded_amount": None,
        }
        return {
            "message": "Invoice created for supplier wallet",
            "invoice": enrich_invoice(invoice),
            "wallets": wallet_snapshot(),
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/invoices/{invoice_id}/fund")
def fund_invoice_for_investor(invoice_id: Union[int, str], req: FundInvoiceReq | None = None):
    try:
        invoice = fetch_invoice_by_id(invoice_id)
        amount = int(float(invoice["amount"]))
        funded_amount = int(round(amount * 0.9))
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid invoice amount")
        if invoice.get("owner") != SUPPLIER_WALLET:
            raise HTTPException(status_code=400, detail="Only supplier-owned invoices can be funded")
        if wallet_state["investor"]["balance"] < funded_amount:
            raise HTTPException(status_code=400, detail="Investor balance is insufficient")

        wallet_state["investor"]["balance"] -= funded_amount
        wallet_state["supplier"]["balance"] += funded_amount
        invoice_financing[str(invoice_id)] = {
            "face_amount": amount,
            "discount_rate": 0.1,
            "funded_amount": funded_amount,
        }

        updated = update_invoice_funded_record(
            invoice_id=invoice_id,
            owner=INVESTOR_WALLET,
            algo_tx_id=f"fund-{invoice_id}",
        )
        return {
            "message": "Funding completed successfully",
            "invoice": enrich_invoice(updated),
            "wallets": wallet_snapshot(),
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/invoices/{invoice_id}/buyer-fund")
def fund_invoice_for_buyer(invoice_id: Union[int, str]):
    try:
        invoice = fetch_invoice_by_id(invoice_id)
        enriched = enrich_invoice(invoice)
        buyer_id = enriched.get("buyer_id", "")
        if not buyer_id or buyer_id not in buyer_accounts:
            raise HTTPException(status_code=404, detail="Buyer account not found for this invoice")

        face_amount = int(float(enriched.get("face_amount") or invoice["amount"]))
        if buyer_accounts[buyer_id]["balance"] < face_amount:
            raise HTTPException(status_code=400, detail="Buyer balance is insufficient")

        buyer_accounts[buyer_id]["balance"] -= face_amount

        if invoice.get("status") == "FUNDED":
            wallet_state["investor"]["balance"] += face_amount
            recipient = "investor"
        else:
            wallet_state["supplier"]["balance"] += face_amount
            recipient = "supplier"

        updated = update_invoice_status_record(invoice_id=invoice_id, status="PAID")
        return {
            "message": "Buyer payment completed successfully",
            "invoice": enrich_invoice(updated),
            "wallets": wallet_snapshot(),
            "recipient": recipient,
            "buyer_balance": buyer_accounts[buyer_id]["balance"],
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: Union[int, str]):
    try:
        return {
            "invoice": enrich_invoice(fetch_invoice_by_id(invoice_id)),
            "wallets": wallet_snapshot(),
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=404, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
