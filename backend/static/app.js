document.addEventListener('DOMContentLoaded', () => {
    const PERA_CHAIN_ID = 416002;
    const deployStatus = document.getElementById('deployStatus');
    const stateOutput = document.getElementById('stateOutput');
    const asaOutput = document.getElementById('asaOutput');
    let pollInterval;
    let peraWallet = null;
    let connectedAccount = '';
    let pendingTokenizeTxn = '';
    let pendingFundTxns = [];
    let signedGroupByInvestor = [];
    let signedGroupBySupplier = [];

    async function req(url, method = 'GET', body = null) {
        const options = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) options.body = JSON.stringify(body);
        const res = await fetch(url, options);
        if (!res.ok) {
            const data = await res.json();
            throw new Error(data.detail || data.error || 'Unknown error');
        }
        return await res.json();
    }

    function toBase64(value) {
        if (!value) return '';
        if (typeof value === 'string') return value;
        if (value instanceof Uint8Array) {
            let binary = '';
            value.forEach(byte => binary += String.fromCharCode(byte));
            return btoa(binary);
        }
        if (value && value.data && Array.isArray(value.data)) {
            return toBase64(new Uint8Array(value.data));
        }
        return '';
    }

    function writeAsaOutput(data) {
        if (!asaOutput) return;
        asaOutput.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    }

    async function signGroupWithPera(unsignedTxns, signerAddress, signerIndex) {
        if (!peraWallet) {
            throw new Error('Pera Wallet is not connected');
        }
        if (!connectedAccount || connectedAccount !== signerAddress) {
            throw new Error(`Connect wallet as signer: ${signerAddress}`);
        }

        const txnsToSign = unsignedTxns.map((txn, idx) => ({
            txn,
            signers: idx === signerIndex ? [signerAddress] : [],
        }));

        const signed = await peraWallet.signTransaction([txnsToSign]);
        const signedGroup = Array.isArray(signed) ? signed : [];
        return signedGroup.map(toBase64);
    }

    async function updateState() {
        try {
            const data = await req('/status');
            stateOutput.textContent = JSON.stringify(data, null, 2);
        } catch(e) {
            stateOutput.textContent = `Error loading state: ${e.message}`;
        }
    }

    const btnDeploy = document.getElementById('btnDeploy');
    const btnCreate = document.getElementById('btnCreate');
    const btnRequestFinancing = document.getElementById('btnRequestFinancing');
    const btnFund = document.getElementById('btnFund');
    const btnRefresh = document.getElementById('btnRefresh');

    if (btnDeploy) {
        btnDeploy.addEventListener('click', async () => {
            deployStatus.textContent = 'Disabled: backend signing removed. Use the ASA wallet flow section below.';
        });
    }

    if (btnCreate) {
        btnCreate.addEventListener('click', async () => {
            alert('Disabled: backend signing removed. Use ASA wallet flow: Prepare Tokenize Txn.');
        });
    }

    if (btnRequestFinancing) {
        btnRequestFinancing.addEventListener('click', async () => {
            alert('Disabled: backend signing removed. Use ASA wallet flow only.');
        });
    }

    if (btnFund) {
        btnFund.addEventListener('click', async () => {
            alert('Disabled: backend signing removed. Use ASA wallet flow: Prepare Funding Group + wallet signatures.');
        });
    }

    if (btnRefresh) {
        btnRefresh.addEventListener('click', updateState);
    }

    const btnConnectWallet = document.getElementById('btnConnectWallet');
    const btnPrepareTokenize = document.getElementById('btnPrepareTokenize');
    const btnSignSubmitTokenize = document.getElementById('btnSignSubmitTokenize');
    const btnPrepareFund = document.getElementById('btnPrepareFund');
    const btnSignInvestor = document.getElementById('btnSignInvestor');
    const btnSignSupplier = document.getElementById('btnSignSupplier');
    const btnSubmitFund = document.getElementById('btnSubmitFund');
    const btnVerifyAsa = document.getElementById('btnVerifyAsa');

    if (btnConnectWallet) {
        btnConnectWallet.addEventListener('click', async () => {
            try {
                if (!peraWallet) {
                    const sdk = window.PeraWalletConnect;
                    let WalletCtor = null;

                    if (typeof sdk === 'function') {
                        WalletCtor = sdk;
                    } else if (sdk && typeof sdk.PeraWalletConnect === 'function') {
                        WalletCtor = sdk.PeraWalletConnect;
                    } else if (window.perawallet && typeof window.perawallet.PeraWalletConnect === 'function') {
                        WalletCtor = window.perawallet.PeraWalletConnect;
                    }

                    if (!WalletCtor) {
                        throw new Error('Pera Wallet SDK not loaded. Refresh page once and try again.');
                    }

                    peraWallet = new WalletCtor({ chainId: PERA_CHAIN_ID });
                }

                const accounts = await peraWallet.connect();
                connectedAccount = (accounts && accounts[0]) || '';
                if (!connectedAccount) {
                    throw new Error('Wallet connected but no account was returned');
                }
                writeAsaOutput({
                    message: 'Wallet connected',
                    account: connectedAccount,
                    chainId: PERA_CHAIN_ID,
                });
            } catch (err) {
                if (err?.data?.type === 'CONNECT_MODAL_CLOSED') {
                    writeAsaOutput('Wallet connect cancelled (modal closed).');
                    return;
                }
                writeAsaOutput(`Wallet connect error: ${err.message}`);
            }
        });
    }

    if (btnPrepareTokenize) {
        btnPrepareTokenize.addEventListener('click', async () => {
            try {
                const supplier = document.getElementById('asaSupplier').value.trim();
                const amount = parseInt(document.getElementById('asaAmount').value || '0', 10);
                if (!supplier) throw new Error('Supplier address is required');
                if (!amount || amount <= 0) throw new Error('Amount must be > 0');

                const data = await req('/asa/invoices/create/prepare', 'POST', { supplier, amount });
                pendingTokenizeTxn = data.unsigned_txn;
                document.getElementById('asaInvoiceId').value = data.invoice.id;
                writeAsaOutput(data);
            } catch (err) {
                writeAsaOutput(`Prepare tokenize error: ${err.message}`);
            }
        });
    }

    if (btnSignSubmitTokenize) {
        btnSignSubmitTokenize.addEventListener('click', async () => {
            try {
                const invoiceId = parseInt(document.getElementById('asaInvoiceId').value || '0', 10);
                if (!invoiceId) throw new Error('Invoice ID is required');
                if (!pendingTokenizeTxn) throw new Error('Prepare tokenize transaction first');
                if (!peraWallet || !connectedAccount) throw new Error('Connect wallet first');

                const signed = await peraWallet.signTransaction([[{ txn: pendingTokenizeTxn }]]);
                const signedTxn = toBase64(Array.isArray(signed) ? signed[0] : signed);
                const data = await req('/asa/invoices/create/submit', 'POST', {
                    invoice_id: invoiceId,
                    signed_txn: signedTxn,
                });
                writeAsaOutput(data);
            } catch (err) {
                writeAsaOutput(`Tokenize submit error: ${err.message}`);
            }
        });
    }

    if (btnPrepareFund) {
        btnPrepareFund.addEventListener('click', async () => {
            try {
                const invoiceId = parseInt(document.getElementById('asaInvoiceId').value || '0', 10);
                const investor = document.getElementById('asaInvestor').value.trim();
                if (!invoiceId) throw new Error('Invoice ID is required');
                if (!investor) throw new Error('Investor address is required');

                const data = await req(`/asa/invoices/${invoiceId}/fund/prepare`, 'POST', { investor });
                pendingFundTxns = data.unsigned_group_txns || [];
                signedGroupByInvestor = [];
                signedGroupBySupplier = [];
                writeAsaOutput(data);
            } catch (err) {
                writeAsaOutput(`Prepare fund error: ${err.message}`);
            }
        });
    }

    if (btnSignInvestor) {
        btnSignInvestor.addEventListener('click', async () => {
            try {
                const investor = document.getElementById('asaInvestor').value.trim();
                if (!pendingFundTxns.length) throw new Error('Prepare funding group first');
                signedGroupByInvestor = await signGroupWithPera(pendingFundTxns, investor, 0);
                writeAsaOutput({ message: 'Investor signature captured', signedGroupByInvestor });
            } catch (err) {
                writeAsaOutput(`Investor sign error: ${err.message}`);
            }
        });
    }

    if (btnSignSupplier) {
        btnSignSupplier.addEventListener('click', async () => {
            try {
                const supplier = document.getElementById('asaSupplier').value.trim();
                if (!pendingFundTxns.length) throw new Error('Prepare funding group first');
                signedGroupBySupplier = await signGroupWithPera(pendingFundTxns, supplier, 1);
                writeAsaOutput({ message: 'Supplier signature captured', signedGroupBySupplier });
            } catch (err) {
                writeAsaOutput(`Supplier sign error: ${err.message}`);
            }
        });
    }

    if (btnSubmitFund) {
        btnSubmitFund.addEventListener('click', async () => {
            try {
                const invoiceId = parseInt(document.getElementById('asaInvoiceId').value || '0', 10);
                const investor = document.getElementById('asaInvestor').value.trim();
                if (!invoiceId) throw new Error('Invoice ID is required');
                if (!investor) throw new Error('Investor address is required');

                const signedTx1 = signedGroupByInvestor[0];
                const signedTx2 = signedGroupBySupplier[1];
                if (!signedTx1 || !signedTx2) {
                    throw new Error('Need both investor and supplier signatures before submit');
                }

                const data = await req(`/asa/invoices/${invoiceId}/fund/submit`, 'POST', {
                    investor,
                    signed_txns: [signedTx1, signedTx2],
                });
                writeAsaOutput(data);
            } catch (err) {
                writeAsaOutput(`Fund submit error: ${err.message}`);
            }
        });
    }

    if (btnVerifyAsa) {
        btnVerifyAsa.addEventListener('click', async () => {
            try {
                const invoiceId = parseInt(document.getElementById('asaInvoiceId').value || '0', 10);
                if (!invoiceId) throw new Error('Invoice ID is required');
                const data = await req(`/asa/invoices/${invoiceId}/verify`, 'GET');
                writeAsaOutput(data);
            } catch (err) {
                writeAsaOutput(`Verify error: ${err.message}`);
            }
        });
    }
});
