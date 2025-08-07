document.addEventListener('DOMContentLoaded', function () {
    let attempts = 0;

    // Add "Total Price" column to table header
    const tableHeadRow = document.querySelector('.inline-group table thead tr');
    if (tableHeadRow && !document.getElementById('total-price-header')) {
        const th = document.createElement('th');
        th.textContent = 'Total Price';
        th.id = 'total-price-header';
        tableHeadRow.insertBefore(th, tableHeadRow.lastElementChild);
    }

    function tryInit() {
        if (typeof window.productPrices !== 'undefined') {
            initOrderItemJS();
        } else if (attempts < 10) {
            attempts++;
            setTimeout(tryInit, 100);
        } else {
            console.error('❌ window.productPrices was never defined.');
        }
    }

    function initOrderItemJS() {
        console.log('✅ productPrices loaded:', window.productPrices);
        const table = document.querySelector('.inline-group table');
        if (!table) {
            console.warn('⚠️ Could not find inline table.');
            return;
        }

        const tbody = table.querySelector('tbody');
        const rows = tbody.querySelectorAll('tr.form-row');
        rows.forEach(initRow);

        addTotalSummaryRow(tbody);
        updateGrandTotal();

        document.body.addEventListener('formset:added', function (e) {
            const newRow = e.target;
            initRow(newRow);
            updateGrandTotal();
        });
    }

    function initRow(row) {
        const quantityInput = row.querySelector('input[id$="-quantity"]');
        const priceInput = row.querySelector('input[id$="-price"]');
        const priceDisplay = row.querySelector('td.field-price p');
        const productSelect = row.querySelector('select[id$="-product"]');
        const deleteCheckbox = row.querySelector('input[type="checkbox"][id$="-DELETE"]');

        if (!quantityInput || (!priceInput && !priceDisplay) || !productSelect) return;

        // Add ID to <p> for easy access later
        if (priceDisplay && row.id) {
            priceDisplay.id = `price-${row.id}`;
        }

        // Add total cell if not exists
        let totalTd = row.querySelector('.line-total');
        if (!totalTd) {
            totalTd = document.createElement('td');
            totalTd.classList.add('line-total');
            totalTd.innerText = '0.00';

            const deleteTd = row.querySelector('td.delete');
            if (deleteTd) {
                row.insertBefore(totalTd, deleteTd);
            } else {
                row.appendChild(totalTd);
            }
        }

        function getPriceValue() {
            if (priceInput) {
                return parseFloat(priceInput.value) || 0;
            } else if (priceDisplay) {
                return parseFloat(priceDisplay.textContent) || 0;
            }
            return 0;
        }

        function updateLineTotal() {
            const quantity = parseFloat(quantityInput.value) || 0;
            const price = getPriceValue();
            const total = quantity * price;
            totalTd.innerText = total.toFixed(2);
            updateGrandTotal();
        }

        function updatePriceFromProduct() {
            const productId = productSelect.value;
            const newPrice = window.productPrices[productId];
            if (priceInput && newPrice !== undefined) {
                priceInput.value = newPrice;
            } else if (priceDisplay && newPrice !== undefined) {
                priceDisplay.textContent = newPrice;
            }
            updateLineTotal();
        }

        quantityInput.addEventListener('input', updateLineTotal);
        if (priceInput) priceInput.addEventListener('input', updateLineTotal);
        productSelect.addEventListener('change', updatePriceFromProduct);

        updatePriceFromProduct();
        updateLineTotal();

        if (deleteCheckbox) {
            deleteCheckbox.addEventListener('change', function () {
                row.style.display = this.checked ? 'none' : '';
                updateGrandTotal();
            });
            row.style.display = deleteCheckbox.checked ? 'none' : '';
        }

        // Remove add/view-related links
        row.querySelectorAll('a.add-related, a.view-related').forEach(a => a.remove());
    }

    function addTotalSummaryRow(tbody) {
        let summaryRow = document.getElementById('order-summary-row');
        if (!summaryRow) {
            summaryRow = document.createElement('tr');
            summaryRow.id = 'order-summary-row';
            const tdCount = tbody.querySelector('tr')?.children.length || 4;

            for (let i = 0; i < tdCount - 1; i++) {
                summaryRow.appendChild(document.createElement('td'));
            }

            const totalTd = document.createElement('td');
            totalTd.colSpan = 1;
            totalTd.innerHTML = '<strong>Total:</strong> <span id="grand-total">0.00</span>';
            summaryRow.appendChild(totalTd);

            tbody.appendChild(summaryRow);
        }
    }

    function updateGrandTotal() {
        const lineTotals = document.querySelectorAll('.line-total');
        let grandTotal = 0;
        lineTotals.forEach(td => {
            const row = td.closest('tr');
            if (row && row.style.display !== 'none') {
                const val = parseFloat(td.innerText) || 0;
                grandTotal += val;
            }
        });
        const display = document.getElementById('grand-total');
        if (display) {
            display.innerText = grandTotal.toFixed(2);
        }
    }

    tryInit();
});
