const orderForm = document.querySelector('.customer-order-form');
const confirmationDialog = document.querySelector('#order-confirmation');

if (orderForm && confirmationDialog) {
    const confirmButton = confirmationDialog.querySelector('[data-submit-order]');
    const cancelButton = confirmationDialog.querySelector('[data-cancel-order]');
    const receiptName = confirmationDialog.querySelector('#receipt-name');
    const receiptPhone = confirmationDialog.querySelector('#receipt-phone');
    const receiptPayment = confirmationDialog.querySelector('#receipt-payment');
    const receiptItems = confirmationDialog.querySelector('#receipt-items');
    const receiptTotal = confirmationDialog.querySelector('#receipt-total');
    let submissionConfirmed = false;

    const currency = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });

    const getSelectedItems = () => [...orderForm.querySelectorAll('.menu-item')]
        .map((menuItem) => {
            const quantity = Number(menuItem.querySelector('.quantity-input').value) || 0;
            const unitPrice = Number((menuItem.dataset.price || '').replace(/[^0-9.-]/g, ''));

            return {
                name: menuItem.querySelector('.menu-item-name').textContent.trim(),
                quantity,
                unitPrice: Number.isFinite(unitPrice) ? unitPrice : 0,
            };
        })
        .filter((item) => item.quantity > 0);

    const populateReceipt = (items) => {
        receiptName.textContent = orderForm.querySelector('[name="customer_name"]').value.trim();
        receiptPhone.textContent = orderForm.querySelector('[name="customer_phone"]').value.trim();
        const selectedPayment = orderForm.querySelector('[name="payment_method"]:checked');
        receiptPayment.textContent = selectedPayment?.value === 'etransfer'
            ? 'E-transfer to mudika@gmail.com'
            : 'Cash';
        receiptItems.replaceChildren();

        let total = 0;
        items.forEach((item) => {
            const lineTotal = Math.round((item.unitPrice * item.quantity + Number.EPSILON) * 100) / 100;
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

    orderForm.addEventListener('submit', (event) => {
        if (submissionConfirmed) {
            submissionConfirmed = false;
            return;
        }

        const items = getSelectedItems();
        if (items.length === 0) {
            return;
        }

        event.preventDefault();
        populateReceipt(items);
        confirmationDialog.showModal();
    });

    cancelButton.addEventListener('click', () => confirmationDialog.close());

    confirmButton.addEventListener('click', () => {
        submissionConfirmed = true;
        confirmationDialog.close();
        orderForm.requestSubmit();
    });
}
