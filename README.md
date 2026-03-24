# Credixa

Credixa is an invoice financing platform prototype built around three roles:

- Supplier: the business that needs money now
- Investor: the party that advances money at a discount
- Buyer: the party that ultimately owes the full invoice amount

The current version is optimized for a smooth role-based product demo. It uses predefined wallet identities, separate login pages for each role, invoice cards on the frontend, and a simplified funding flow so the lifecycle is easy to explain and record in a short walkthrough.

## Project Overview

In a real invoice financing workflow, a supplier issues an invoice to a buyer, but may not want to wait for the buyer to pay. An investor can step in, provide early liquidity to the supplier for a discounted amount, and later collect the full invoice amount from the buyer.

Credixa models that lifecycle as:

1. Supplier logs in and creates an invoice for a buyer
2. Investor logs in and funds that invoice for a lower upfront amount
3. Ownership of the invoice shifts to the investor
4. Buyer logs in and pays the full amount later

This repository combines:

- a FastAPI backend
- a multi-page frontend served from static HTML/CSS/JS
- invoice persistence through Supabase when available
- an in-memory fallback for easier demos
- Algorand-oriented contract and asset tooling for invoice tokenization experiments

## Core Features

- Separate role flows for Supplier, Investor, and Buyer
- Separate login pages and dashboards for each role
- Supplier invoice creation with buyer assignment
- Investor funding with discounted upfront payment logic
- Buyer-side payment flow
- Popup-based action feedback for demos
- Invoice cards instead of raw JSON/debug panels
- Reset support to restart the system from invoice `1`
- Predefined Algorand wallet identities for presentation-friendly walkthroughs

## Tech Stack

### Frontend

- HTML pages served from `backend/static`
- Vanilla JavaScript bundled with `esbuild`
- Custom CSS for the multi-page UI

### Backend

- FastAPI
- Uvicorn
- Pydantic
- Python 3

### Data

- Supabase for persistent invoice storage
- In-memory fallback when Supabase is unavailable

### Algorand Tooling

- `py-algorand-sdk`
- `algosdk`
- `algokit-utils`
- `algopy`

## Why Algorand

Credixa is designed around the idea that invoices can be represented and transferred digitally in a transparent, verifiable way. Algorand is a good fit for that because it offers:

- fast finality
- low transaction costs
- native asset support
- strong smart contract tooling
- standards-based interoperability

## Algorand Components Used

### ASA

ASA stands for Algorand Standard Asset.

Why it matters here:

- an invoice can be represented as a unique on-chain asset
- ownership transfer becomes an asset transfer
- the investor becoming the new holder can be tracked clearly
- it gives a natural model for tokenized invoice ownership

In this project, the current UI is focused on a simplified demo flow, but the codebase includes the foundations for invoice tokenization and asset-style ownership transitions.

### ARC Standards

ARC stands for Algorand Request for Comments. These are community standards that make Algorand apps easier to integrate, describe, and interact with.

The repository includes an ARC-based contract approach through:

- [smart_contract.py](/c:/Users/Charmi/Desktop/Projects/Credixa/backend/smart_contract.py)
- [InvoiceFinancing.arc56.json](/c:/Users/Charmi/Desktop/Projects/Credixa/backend/backend/artifacts/InvoiceFinancing.arc56.json)

### ARC-4

The smart contract in [smart_contract.py](/c:/Users/Charmi/Desktop/Projects/Credixa/backend/smart_contract.py) is written with `algopy.ARC4Contract`.

Why ARC-4 is used:

- it provides a standard ABI contract interface
- it makes contract methods easier to call and reason about
- it maps cleanly to operations like:
  - `create_invoice`
  - `request_financing`
  - `fund_invoice`
  - `settle_invoice`

### ARC-56

The generated artifact [InvoiceFinancing.arc56.json](/c:/Users/Charmi/Desktop/Projects/Credixa/backend/backend/artifacts/InvoiceFinancing.arc56.json) provides a structured contract description.

Why ARC-56 is useful:

- it documents the contract interface in a machine-readable way
- it helps frontend/backend tooling understand callable methods
- it improves integration with AlgoKit-style workflows and contract clients

## Important Files

- [backend/app.py](/c:/Users/Charmi/Desktop/Projects/Credixa/backend/app.py)
  Main FastAPI backend, page routing, auth endpoints, invoice logic, funding logic, and system reset

- [frontend-src/app-entry.js](/c:/Users/Charmi/Desktop/Projects/Credixa/frontend-src/app-entry.js)
  Frontend logic for login, registration, redirects, invoice actions, card rendering, and popups

- [backend/db.py](/c:/Users/Charmi/Desktop/Projects/Credixa/backend/db.py)
  Invoice persistence layer with Supabase support and in-memory fallback

- [backend/wallet_config.py](/c:/Users/Charmi/Desktop/Projects/Credixa/backend/wallet_config.py)
  Predefined supplier, investor, and buyer wallet addresses plus starting balances

- [backend/static/styles.css](/c:/Users/Charmi/Desktop/Projects/Credixa/backend/static/styles.css)
  Shared styling for landing, login, and dashboard pages

- [backend/smart_contract.py](/c:/Users/Charmi/Desktop/Projects/Credixa/backend/smart_contract.py)
  Algorand contract definition for invoice lifecycle methods

- [backend/backend/artifacts/InvoiceFinancing.arc56.json](/c:/Users/Charmi/Desktop/Projects/Credixa/backend/backend/artifacts/InvoiceFinancing.arc56.json)
  ARC-56 contract artifact describing the app interface

## Setup

### 1. Clone the project

```powershell
git clone <your-repo-url>
cd Credixa
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install backend dependencies

```powershell
pip install -r requirements.txt
```

### 4. Install frontend dependencies

```powershell
npm install
```

### 5. Optional: configure Supabase

Copy `.env.example` to `.env` and set:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- optionally wallet and balance overrides such as:
  - `SUPPLIER_WALLET`
  - `INVESTOR_WALLET`
  - `BUYER_WALLET`
  - `SUPPLIER_STARTING_BALANCE`
  - `INVESTOR_STARTING_BALANCE`

If Supabase is not configured, the app still runs using in-memory invoice storage.

### 6. Build the frontend bundle

```powershell
npm run build:app
```

### 7. Run the app

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

## Useful Scripts

```powershell
npm run build:app
npm run build:app:watch
```

## Demo Flow

For a short walkthrough:

1. Open the landing page and choose a role
2. Login as Supplier and create an invoice for a buyer
3. Login as Investor and fund the invoice
4. Show that the invoice holder changes to the investor
5. Login as Buyer and complete the payment step

## Notes

- The current UI is intentionally optimized for a short, understandable demo
- The repository still includes real Algorand-oriented building blocks such as ASA thinking, ARC-4 contract structure, and ARC-56 artifacts
- Supabase persistence is supported, but the app can also run without it for easier local demos
