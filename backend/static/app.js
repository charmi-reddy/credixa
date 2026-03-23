document.addEventListener('DOMContentLoaded', () => {
    const deployStatus = document.getElementById('deployStatus');
    const stateOutput = document.getElementById('stateOutput');
    let pollInterval;

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

    async function updateState() {
        try {
            const data = await req('/status');
            stateOutput.textContent = JSON.stringify(data, null, 2);
        } catch(e) {
            stateOutput.textContent = `Error loading state: ${e.message}`;
        }
    }

    document.getElementById('btnDeploy').addEventListener('click', async (e) => {
        try {
            e.target.disabled = true;
            e.target.textContent = 'Deploying...';
            deployStatus.textContent = '';
            
            const data = await req('/deploy', 'POST');
            deployStatus.textContent = `App ID: ${data.app_id} | Supplier: ${data.supplier.slice(0,8)}... | Investor: ${data.investor.slice(0,8)}...`;
            
            await updateState();
            
            if(!pollInterval) {
                pollInterval = setInterval(updateState, 3000);
            }
        } catch(err) {
            alert('Deploy Error: ' + err.message);
        } finally {
            e.target.disabled = false;
            e.target.textContent = 'Deploy Contract';
        }
    });

    document.getElementById('btnCreate').addEventListener('click', async (e) => {
        const amount = document.getElementById('invoiceAmount').value || 0;
        try {
            e.target.disabled = true;
            await req('/create_invoice', 'POST', { amount: parseInt(amount) });
            await updateState();
            alert('Invoice created successfully!');
        } catch(err) {
            alert('Create Error: ' + err.message);
        } finally {
            e.target.disabled = false;
        }
    });

    document.getElementById('btnRequestFinancing').addEventListener('click', async (e) => {
        try {
            e.target.disabled = true;
            await req('/request_financing', 'POST');
            await updateState();
            alert('Financing requested!');
        } catch(err) {
            alert('Request Error: ' + err.message);
        } finally {
            e.target.disabled = false;
        }
    });

    document.getElementById('btnFund').addEventListener('click', async (e) => {
        try {
            e.target.disabled = true;
            e.target.textContent = 'Processing Atomic Transaction...';
            await req('/fund_invoice', 'POST');
            await updateState();
            alert('Invoice funded atomically!');
        } catch(err) {
            alert('Fund Error: ' + err.message);
        } finally {
            e.target.disabled = false;
            e.target.textContent = 'Fund Atomically';
        }
    });

    document.getElementById('btnRefresh').addEventListener('click', updateState);
});
