// ---------- Running total on the customer page ----------
const totalDisplay = document.querySelector('#order-total-amount');

const updateOrderTotal = () => {
    if (!totalDisplay) {
        return;
    }

    const total = [...document.querySelectorAll('.menu-item')].reduce((sum, menuItem) => {
        const price = Number(menuItem.dataset.price) || 0;
        const quantity = Number(menuItem.querySelector('.quantity-input').value) || 0;
        return sum + price * quantity;
    }, 0);

    totalDisplay.textContent = new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(total);
};

// ---------- + / - quantity buttons ----------
document.querySelectorAll('.menu-item').forEach((menuItem) => {
    const quantityInput = menuItem.querySelector('.quantity-input');
    const minusButton = menuItem.querySelector('.quantity-minus');
    const plusButton = menuItem.querySelector('.quantity-plus');
    const minimum = Number(quantityInput.dataset.min) || 0;  // admin's "quantity minimum"
    const maximum = quantityInput.max === '' ? Infinity : Number(quantityInput.max);

    const setQuantity = (quantity) => {
        quantityInput.value = quantity <= 0
            ? 0
            : Math.min(maximum, Math.max(minimum, quantity));
    };

    minusButton.addEventListener('click', () => {
        const quantity = Number(quantityInput.value) || 0;
        setQuantity(quantity <= minimum ? 0 : quantity - 1);
        updateOrderTotal();
    });

    plusButton.addEventListener('click', () => {
        const quantity = Number(quantityInput.value) || 0;
        setQuantity(quantity === 0 ? Math.max(minimum, 1) : quantity + 1);
        updateOrderTotal();
    });

    quantityInput.addEventListener('input', () => {
        if (quantityInput.value !== '') {
            setQuantity(Number(quantityInput.value) || 0);
        }
        updateOrderTotal();
    });

    quantityInput.addEventListener('change', () => {
        setQuantity(Number(quantityInput.value) || 0);
        updateOrderTotal();
    });
});

updateOrderTotal();

// ---------- "Are you sure?" for admin delete buttons ----------
document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
        if (!window.confirm(form.dataset.confirm)) {
            event.preventDefault();
        }
    });
});
