// "Review your order" pop-up on the customer page.
// When the customer presses "Submit order", we stop the form, fill in the pop-up
// with what they chose, and only really submit after they press "Yes, submit now".

const orderForm = document.querySelector('.customer-order-form');
const confirmationDialog = document.querySelector('#order-confirmation');

if (orderForm && confirmationDialog) {
    const confirmButton = confirmationDialog.querySelector('[data-submit-order]');
    const cancelButton = confirmationDialog.querySelector('[data-cancel-order]');
    const receiptName = confirmationDialog.querySelector('#receipt-name');
    const receiptPhone = confirmationDialog.querySelector('#receipt-phone');
    const receiptPayment = confirmationDialog.querySelector('#receipt-payment');
    const receiptInfoRow = confirmationDialog.querySelector('#receipt-additional-info-row');
    const receiptInfo = confirmationDialog.querySelector('#receipt-additional-info');
    const receiptItems = confirmationDialog.querySelector('#receipt-items');
    const receiptTotal = confirmationDialog.querySelector('#receipt-total');
    const etransferEmail = orderForm.dataset.etransferEmail || '';
    let submissionConfirmed = false;

    const currency = new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' });

    // ---------- Read the customer's choices from the form ----------
    const getSelectedItems = () => [...orderForm.querySelectorAll('.menu-item')]
        .map((menuItem) => ({
            name: menuItem.querySelector('.menu-item-name').textContent.trim(),
            quantity: Number(menuItem.querySelector('.quantity-input').value) || 0,
            unitPrice: Number(menuItem.dataset.price) || 0,
        }))
        .filter((item) => item.quantity > 0);

    // ---------- Fill in the pop-up ----------
    const populateReceipt = (items) => {
        receiptName.textContent = orderForm.querySelector('[name="customer_name"]').value.trim();
        receiptPhone.textContent = orderForm.querySelector('[name="customer_phone"]').value.trim();

        const selectedPayment = orderForm.querySelector('[name="payment_method"]:checked');
        if (selectedPayment?.value === 'etransfer') {
            receiptPayment.textContent = etransferEmail ? `E-transfer to ${etransferEmail}` : 'E-transfer';
        } else {
            receiptPayment.textContent = 'Cash';
        }

        const additionalInfo = orderForm.querySelector('[name="additional_info"]').value.trim();
        receiptInfo.textContent = additionalInfo;
        receiptInfoRow.hidden = additionalInfo === '';

        receiptItems.replaceChildren();
        let total = 0;
        items.forEach((item) => {
            const lineTotal = Math.round(item.unitPrice * item.quantity * 100) / 100;
            total += lineTotal;

            const row = document.createElement('li');
            row.className = 'receipt-item';

            const description = document.createElement('div');
            description.className = 'receipt-item-description';

            const name = document.createElement('span');
            name.className = 'receipt-item-name';
            name.textContent = item.name;

            const quantity = document.createElement('span');
            quantity.className = 'receipt-item-quantity';
            quantity.textContent = `${item.quantity} ${item.quantity === 1 ? 'pc' : 'pcs'}`;

            const price = document.createElement('strong');
            price.className = 'receipt-item-price';
            price.textContent = currency.format(lineTotal);

            description.append(name, quantity);
            row.append(description, price);
            receiptItems.append(row);
        });
        receiptTotal.textContent = currency.format(total);
    };

    // ---------- Buttons ----------
    orderForm.addEventListener('submit', (event) => {
        if (submissionConfirmed) {
            submissionConfirmed = false;
            return; // the customer already pressed "Yes, submit now"
        }
        const items = getSelectedItems();
        if (items.length === 0) {
            return; // let the server show "Choose at least one item"
        }
        event.preventDefault();
        populateReceipt(items);
        confirmationDialog.showModal();
    });

    cancelButton.addEventListener('click', () => confirmationDialog.close());

    confirmButton.addEventListener('click', () => {
        submissionConfirmed = true;
        confirmButton.disabled = true; // prevent double orders from double clicks
        confirmationDialog.close();
        orderForm.requestSubmit();
    });
}
