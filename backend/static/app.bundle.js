(() => {
  // frontend-src/app-entry.js
  function shortenAddress(address) {
    if (!address) return "";
    if (address.length <= 12) return address;
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  }
  function getPage() {
    return document.body.dataset.page || "";
  }
  function getAuth(role) {
    try {
      return JSON.parse(localStorage.getItem(`credixa_auth_${role}`) || "null");
    } catch (_) {
      return null;
    }
  }
  function setAuth(role, data) {
    localStorage.setItem(`credixa_auth_${role}`, JSON.stringify(data));
  }
  function clearAllAuth() {
    ["supplier", "investor", "buyer"].forEach((role) => localStorage.removeItem(`credixa_auth_${role}`));
  }
  async function req(url, method = "GET", body = null) {
    const options = { method, headers: { "Content-Type": "application/json" } };
    if (body) options.body = JSON.stringify(body);
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || data.error || `Request failed: ${res.status}`);
    return data;
  }
  function popupApi() {
    const popup = document.getElementById("popup");
    const popupTag = document.getElementById("popupTag");
    const popupTitle = document.getElementById("popupTitle");
    const popupMessage = document.getElementById("popupMessage");
    const btnClosePopup = document.getElementById("btnClosePopup");
    function show(title, message, tag = "Action") {
      if (!popup) return;
      popupTag.textContent = tag;
      popupTitle.textContent = title;
      popupMessage.textContent = message;
      popup.classList.remove("hidden");
    }
    function hide() {
      popup == null ? void 0 : popup.classList.add("hidden");
    }
    btnClosePopup == null ? void 0 : btnClosePopup.addEventListener("click", hide);
    popup == null ? void 0 : popup.addEventListener("click", (event) => {
      if (event.target === popup) hide();
    });
    return { show, hide };
  }
  function renderWallets(wallets) {
    var _a, _b, _c, _d;
    const supplierWalletStatus = document.getElementById("supplierWalletStatus");
    const investorWalletStatus = document.getElementById("investorWalletStatus");
    const supplierBalance = document.getElementById("supplierBalance");
    const investorBalance = document.getElementById("investorBalance");
    if (!wallets) return;
    if (supplierWalletStatus) supplierWalletStatus.textContent = `${shortenAddress(wallets.supplier || "")}`;
    if (investorWalletStatus) investorWalletStatus.textContent = `${shortenAddress(wallets.investor || "")}`;
    if (supplierBalance) supplierBalance.textContent = `${(_b = (_a = wallets.balances) == null ? void 0 : _a.supplier) != null ? _b : 0} microAlgos`;
    if (investorBalance) investorBalance.textContent = `${(_d = (_c = wallets.balances) == null ? void 0 : _c.investor) != null ? _d : 0} microAlgos`;
  }
  function invoiceCard(invoice, role) {
    const fundedAmount = invoice.funded_amount != null ? `${Number(invoice.funded_amount).toLocaleString()} microAlgos` : "Not funded yet";
    const investorAction = role === "investor" && invoice.status === "CREATED" ? `<button class="btn accent fund-btn" data-invoice-id="${invoice.id}">Fund This Invoice</button>` : "";
    const buyerAction = role === "buyer" && invoice.status !== "PAID" ? `<button class="btn primary buyer-fund-btn" data-invoice-id="${invoice.id}">Fund Now</button>` : "";
    const actions = investorAction || buyerAction;
    return `
        <article class="invoice-card">
            <div class="invoice-top">
                <div>
                    <div class="invoice-label">Invoice #${invoice.id}</div>
                    <h3>${Number(invoice.face_amount || invoice.amount).toLocaleString()} microAlgos</h3>
                </div>
                <span class="invoice-status">${invoice.status}</span>
            </div>
            <div class="invoice-meta">
                <div><span>Buyer ID</span><strong>${invoice.buyer_id || "N/A"}</strong></div>
                <div><span>Owner</span><strong>${shortenAddress(invoice.owner || "")}</strong></div>
                <div><span>Supplier Wallet</span><strong>${invoice.owner === "" ? "N/A" : shortenAddress("CSGNQCBEKLMKWYCCUQ3CHG4H6OORBF5DQ5QEY3BWCLF6XKVRTDGEQTQK5E")}</strong></div>
                <div><span>Funded Amount</span><strong>${fundedAmount}</strong></div>
                <div><span>Reference</span><strong>${invoice.algo_tx_id || "Pending"}</strong></div>
                <div><span>Discount</span><strong>${Math.round((invoice.discount_rate || 0) * 100)}%</strong></div>
            </div>
            ${actions}
        </article>
    `;
  }
  function renderInvoices(invoices, role, filterFn) {
    const grid = document.getElementById("invoiceGrid");
    const empty = document.getElementById("emptyInvoices");
    if (!grid || !empty) return;
    const visible = filterFn ? invoices.filter(filterFn) : invoices;
    if (!visible.length) {
      grid.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");
    grid.innerHTML = visible.map((invoice) => invoiceCard(invoice, role)).join("");
  }
  async function loadDashboard(role, filterFn) {
    const auth = getAuth(role);
    if (!auth) {
      window.location.href = `/${role}/login`;
      return { auth: null, invoices: [] };
    }
    const [wallets, invoiceRes] = await Promise.all([
      req("/wallets"),
      req("/invoices")
    ]);
    renderWallets(wallets);
    renderInvoices(invoiceRes.invoices || [], role, filterFn);
    return { auth, invoices: invoiceRes.invoices || [] };
  }
  document.addEventListener("DOMContentLoaded", () => {
    var _a, _b, _c, _d, _e, _f, _g, _h, _i, _j, _k;
    const page = getPage();
    const popup = popupApi();
    if (page === "supplier-login") {
      (_a = document.getElementById("btnSupplierLogin")) == null ? void 0 : _a.addEventListener("click", async () => {
        try {
          const user_id = document.getElementById("supplierUserId").value.trim();
          const password = document.getElementById("supplierPassword").value.trim();
          const data = await req("/auth/supplier/login", "POST", { user_id, password });
          setAuth("supplier", data);
          popup.show("Supplier login successful", "Redirecting to the supplier dashboard.", "Login");
          setTimeout(() => {
            window.location.href = "/supplier/dashboard";
          }, 500);
        } catch (err) {
          popup.show("Supplier login failed", err.message, "Error");
        }
      });
    }
    if (page === "investor-login") {
      (_b = document.getElementById("btnInvestorLogin")) == null ? void 0 : _b.addEventListener("click", async () => {
        try {
          const user_id = document.getElementById("investorUserId").value.trim();
          const password = document.getElementById("investorPassword").value.trim();
          const data = await req("/auth/investor/login", "POST", { user_id, password });
          setAuth("investor", data);
          popup.show("Investor login successful", "Redirecting to the investor dashboard.", "Login");
          setTimeout(() => {
            window.location.href = "/investor/dashboard";
          }, 500);
        } catch (err) {
          popup.show("Investor login failed", err.message, "Error");
        }
      });
    }
    if (page === "buyer-login") {
      (_c = document.getElementById("btnBuyerLogin")) == null ? void 0 : _c.addEventListener("click", async () => {
        try {
          const buyer_id = document.getElementById("buyerId").value.trim();
          const password = document.getElementById("buyerPassword").value.trim();
          const data = await req("/auth/buyer/login", "POST", { buyer_id, password });
          setAuth("buyer", data);
          popup.show("Buyer login successful", "Redirecting to the buyer dashboard.", "Login");
          setTimeout(() => {
            window.location.href = "/buyer/dashboard";
          }, 500);
        } catch (err) {
          popup.show("Buyer login failed", err.message, "Error");
        }
      });
      (_d = document.getElementById("btnBuyerRegister")) == null ? void 0 : _d.addEventListener("click", async () => {
        try {
          const buyer_id = document.getElementById("buyerId").value.trim();
          const password = document.getElementById("buyerPassword").value.trim();
          const data = await req("/auth/buyer/register", "POST", { buyer_id, password });
          setAuth("buyer", data);
          popup.show("Buyer registered", "Redirecting to the buyer dashboard.", "Registration");
          setTimeout(() => {
            window.location.href = "/buyer/dashboard";
          }, 500);
        } catch (err) {
          popup.show("Buyer registration failed", err.message, "Error");
        }
      });
    }
    if (page === "supplier-dashboard") {
      const refresh = async () => {
        const auth = getAuth("supplier");
        const buyerInput = document.getElementById("buyerIdForInvoice");
        await loadDashboard("supplier");
        document.getElementById("welcomeText").textContent = `Logged in as ${auth == null ? void 0 : auth.user_id}. Create invoices for buyers who will pay later.`;
        if (buyerInput && !buyerInput.value) buyerInput.value = "1234";
      };
      (_e = document.getElementById("btnCreateInvoice")) == null ? void 0 : _e.addEventListener("click", async () => {
        try {
          const buyer_id = document.getElementById("buyerIdForInvoice").value.trim();
          const amount = parseInt(document.getElementById("asaAmount").value || "0", 10);
          if (!buyer_id) throw new Error("Buyer ID is required");
          if (!amount || amount <= 0) throw new Error("Amount must be greater than 0");
          const data = await req(`/invoices/create?buyer_id=${encodeURIComponent(buyer_id)}`, "POST", { amount });
          await refresh();
          popup.show("Invoice created", `Invoice #${data.invoice.id} was created for buyer ${buyer_id}.`, "Invoice");
        } catch (err) {
          popup.show("Invoice creation failed", err.message, "Error");
        }
      });
      (_f = document.getElementById("btnRefresh")) == null ? void 0 : _f.addEventListener("click", async () => {
        await refresh();
        popup.show("Supplier dashboard refreshed", "The latest supplier invoices have been loaded.", "Refresh");
      });
      (_g = document.getElementById("btnLogout")) == null ? void 0 : _g.addEventListener("click", () => {
        clearAllAuth();
        window.location.href = "/";
      });
      refresh().catch((err) => popup.show("Load failed", err.message, "Error"));
    }
    if (page === "investor-dashboard") {
      const refresh = async () => {
        await loadDashboard("investor", (invoice) => invoice.status === "CREATED" || invoice.status === "FUNDED");
        document.querySelectorAll(".fund-btn").forEach((button) => {
          button.addEventListener("click", async () => {
            try {
              const invoiceId = button.dataset.invoiceId;
              const data = await req(`/invoices/${invoiceId}/fund`, "POST", { invoice_id: Number(invoiceId) });
              await refresh();
              popup.show("Invoice funded", `Invoice #${data.invoice.id} was funded at a discounted upfront amount of ${Number(data.invoice.funded_amount).toLocaleString()} microAlgos.`, "Funding");
            } catch (err) {
              popup.show("Funding failed", err.message, "Error");
            }
          });
        });
      };
      (_h = document.getElementById("btnRefresh")) == null ? void 0 : _h.addEventListener("click", async () => {
        await refresh();
        popup.show("Investor dashboard refreshed", "The latest invoices available for funding have been loaded.", "Refresh");
      });
      (_i = document.getElementById("btnLogout")) == null ? void 0 : _i.addEventListener("click", () => {
        clearAllAuth();
        window.location.href = "/";
      });
      refresh().catch((err) => popup.show("Load failed", err.message, "Error"));
    }
    if (page === "buyer-dashboard") {
      const refresh = async () => {
        const auth = getAuth("buyer");
        await loadDashboard("buyer", (invoice) => invoice.buyer_id === (auth == null ? void 0 : auth.buyer_id));
        const welcome = document.getElementById("welcomeText");
        if (welcome) {
          welcome.textContent = `Buyer ${auth == null ? void 0 : auth.buyer_id} can see invoices that will eventually be repaid in full.`;
        }
        document.querySelectorAll(".buyer-fund-btn").forEach((button) => {
          button.addEventListener("click", async () => {
            try {
              const invoiceId = button.dataset.invoiceId;
              const data = await req(`/invoices/${invoiceId}/buyer-fund`, "POST");
              await refresh();
              const target = data.recipient === "investor" ? "investor" : "supplier";
              popup.show("Payment completed", `Invoice #${data.invoice.id} has been paid by the buyer to the ${target}.`, "Payment");
            } catch (err) {
              popup.show("Payment failed", err.message, "Error");
            }
          });
        });
      };
      (_j = document.getElementById("btnRefresh")) == null ? void 0 : _j.addEventListener("click", async () => {
        await refresh();
        popup.show("Buyer dashboard refreshed", "Your assigned invoices have been loaded.", "Refresh");
      });
      (_k = document.getElementById("btnLogout")) == null ? void 0 : _k.addEventListener("click", () => {
        clearAllAuth();
        window.location.href = "/";
      });
      refresh().catch((err) => popup.show("Load failed", err.message, "Error"));
    }
  });
})();
