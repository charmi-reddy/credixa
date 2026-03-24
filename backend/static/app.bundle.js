(() => {
  // frontend-src/app-entry.js
  function initCredixaApp() {
    const deployStatus = document.getElementById("deployStatus");
    const stateOutput = document.getElementById("stateOutput");
    const asaOutput = document.getElementById("asaOutput");
    let pendingTokenizeTxn = "";
    let pendingFundTxns = [];
    async function req(url, method = "GET", body = null) {
      const options = { method, headers: { "Content-Type": "application/json" } };
      if (body) options.body = JSON.stringify(body);
      const res = await fetch(url, options);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || data.error || `Request failed: ${res.status}`);
      }
      return res.json();
    }
    function writeAsaOutput(data) {
      if (!asaOutput) return;
      asaOutput.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    }
    async function updateState() {
      try {
        const data = await req("/status");
        if (stateOutput) {
          stateOutput.textContent = JSON.stringify(data, null, 2);
        }
      } catch (e) {
        if (stateOutput) {
          stateOutput.textContent = `Error loading state: ${e.message}`;
        }
      }
    }
    if (deployStatus) {
      deployStatus.textContent = "Wallet integration reset. Starting fresh from scratch.";
    }
    const btnConnectWallet = document.getElementById("btnConnectWallet");
    const btnPrepareTokenize = document.getElementById("btnPrepareTokenize");
    const btnSignSubmitTokenize = document.getElementById("btnSignSubmitTokenize");
    const btnPrepareFund = document.getElementById("btnPrepareFund");
    const btnSignInvestor = document.getElementById("btnSignInvestor");
    const btnSignSupplier = document.getElementById("btnSignSupplier");
    const btnSubmitFund = document.getElementById("btnSubmitFund");
    const btnVerifyAsa = document.getElementById("btnVerifyAsa");
    const btnRefresh = document.getElementById("btnRefresh");
    if (btnConnectWallet) {
      btnConnectWallet.addEventListener("click", () => {
        writeAsaOutput("Wallet integration has been revoked. Rebuild connect flow from scratch.");
      });
    }
    if (btnPrepareTokenize) {
      btnPrepareTokenize.addEventListener("click", async () => {
        var _a;
        try {
          const supplier = document.getElementById("asaSupplier").value.trim();
          const amount = parseInt(document.getElementById("asaAmount").value || "0", 10);
          if (!supplier) throw new Error("Supplier address is required");
          if (!amount || amount <= 0) throw new Error("Amount must be > 0");
          const data = await req("/asa/invoices/create/prepare", "POST", { supplier, amount });
          pendingTokenizeTxn = data.unsigned_txn || "";
          if ((_a = data == null ? void 0 : data.invoice) == null ? void 0 : _a.id) {
            document.getElementById("asaInvoiceId").value = data.invoice.id;
          }
          writeAsaOutput({
            message: "Prepare tokenize succeeded (wallet signing disabled in reset mode).",
            pendingTokenizeTxn: Boolean(pendingTokenizeTxn),
            data
          });
        } catch (err) {
          writeAsaOutput(`Prepare tokenize error: ${err.message}`);
        }
      });
    }
    if (btnSignSubmitTokenize) {
      btnSignSubmitTokenize.addEventListener("click", () => {
        writeAsaOutput("Tokenize sign/submit disabled. Wallet integration was reset.");
      });
    }
    if (btnPrepareFund) {
      btnPrepareFund.addEventListener("click", async () => {
        try {
          const invoiceId = parseInt(document.getElementById("asaInvoiceId").value || "0", 10);
          const investor = document.getElementById("asaInvestor").value.trim();
          if (!invoiceId) throw new Error("Invoice ID is required");
          if (!investor) throw new Error("Investor address is required");
          const data = await req(`/asa/invoices/${invoiceId}/fund/prepare`, "POST", { investor });
          pendingFundTxns = data.unsigned_group_txns || [];
          writeAsaOutput({
            message: "Prepare fund succeeded (wallet signing disabled in reset mode).",
            pendingFundGroupSize: pendingFundTxns.length,
            data
          });
        } catch (err) {
          writeAsaOutput(`Prepare fund error: ${err.message}`);
        }
      });
    }
    if (btnSignInvestor) {
      btnSignInvestor.addEventListener("click", () => {
        writeAsaOutput("Investor signing disabled. Wallet integration was reset.");
      });
    }
    if (btnSignSupplier) {
      btnSignSupplier.addEventListener("click", () => {
        writeAsaOutput("Supplier signing disabled. Wallet integration was reset.");
      });
    }
    if (btnSubmitFund) {
      btnSubmitFund.addEventListener("click", () => {
        writeAsaOutput("Fund submit disabled. Wallet integration was reset.");
      });
    }
    if (btnVerifyAsa) {
      btnVerifyAsa.addEventListener("click", async () => {
        try {
          const invoiceId = parseInt(document.getElementById("asaInvoiceId").value || "0", 10);
          if (!invoiceId) throw new Error("Invoice ID is required");
          const data = await req(`/asa/invoices/${invoiceId}/verify`, "GET");
          writeAsaOutput(data);
        } catch (err) {
          writeAsaOutput(`Verify error: ${err.message}`);
        }
      });
    }
    if (btnRefresh) {
      btnRefresh.addEventListener("click", updateState);
    }
    updateState();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCredixaApp);
  } else {
    initCredixaApp();
  }
})();
