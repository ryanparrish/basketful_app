document.addEventListener('DOMContentLoaded', function () {
    console.log("🟡 Voucher admin JS loaded");

    function updateVoucherAmount(row) {
        const accountSelect = row.querySelector('select[name$="-account"]');
        const typeSelect = row.querySelector('select[name$="-voucher_type"]');
        const amountInput = row.querySelector('input[name$="-amount"]');

        if (!accountSelect || !typeSelect || !amountInput) return;

        const accountId = accountSelect.value;
        const voucherType = typeSelect.value;

        if (!accountId || !voucherType) return;

        const url = `/admin/voucher/calculate/?account_id=${accountId}&voucher_type=${voucherType}`;

        fetch(url)
            .then(res => res.json())
            .then(data => {
                amountInput.value = data.amount.toFixed(2);
            })
            .catch(err => console.error("❌ Error fetching amount:", err));
    }

    function initVoucherRows() {
        const rows = document.querySelectorAll('tr.form-row');
        rows.forEach(row => {
            const account = row.querySelector('select[name$="-account"]');
            const type = row.querySelector('select[name$="-voucher_type"]');
            if (account) account.addEventListener('change', () => updateVoucherAmount(row));
            if (type) type.addEventListener('change', () => updateVoucherAmount(row));
            updateVoucherAmount(row); // initial update
        });
    }

    initVoucherRows();

    document.body.addEventListener('formset:added', function (e) {
        const newRow = e.target;
        updateVoucherAmount(newRow);
    });
});
