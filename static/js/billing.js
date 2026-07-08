// Ultra High Performance Keyboard-First Billing Javascript

let products = [];
let customers = [];
let selectedProductIndex = -1;
let selectedCustomerIndex = -1;
let billItems = [];
let nextSerial = 1; // Persistent serial number counter
let activeCustomer = null;
let editingRowId = null; // ID of the row being inline edited

// DOM Elements
let elProductSearch, elSuggestions, elQty, elRate, elCustomerSearch, elCustomerPhone, elCustomerSuggestions;
let elBillTableBody, elGrossTotal, elDiscount, elNetTotal, elAmountPaid, elPendingAmount, elOldBalance, elFinalBalance;
let elSrNoNext, elBillForm;

document.addEventListener('DOMContentLoaded', () => {
    initDOMElements();
    loadProducts();
    loadCustomers();
    setupEventListeners();
    resetProductFields();
    
    // Check for session duplicated data
    if (window.duplicatedItems && window.duplicatedItems.length > 0) {
        billItems = window.duplicatedItems;
        renderTable();
    }
    if (window.duplicatedCustomer) {
        activeCustomer = window.duplicatedCustomer;
        elCustomerSearch.value = activeCustomer.name || '';
        elCustomerPhone.value = activeCustomer.phone || '';
        elOldBalance.textContent = parseFloat(activeCustomer.balance || 0).toFixed(2);
    }
    
    recalculateBill();
    elProductSearch.focus();
});

function initDOMElements() {
    elProductSearch = document.getElementById('product-search');
    elSuggestions = document.getElementById('product-suggestions');
    elQty = document.getElementById('product-qty');
    elRate = document.getElementById('product-rate');
    elCustomerSearch = document.getElementById('customer-search');
    elCustomerPhone = document.getElementById('customer-phone');
    elCustomerSuggestions = document.getElementById('customer-suggestions');
    elBillTableBody = document.getElementById('bill-table-body');
    elGrossTotal = document.getElementById('gross-total');
    elDiscount = document.getElementById('discount');
    elNetTotal = document.getElementById('net-total');
    elAmountPaid = document.getElementById('amount-paid');
    elPendingAmount = document.getElementById('pending-amount');
    elOldBalance = document.getElementById('old-balance');
    elFinalBalance = document.getElementById('final-balance');
    elSrNoNext = document.getElementById('sr-no-next');
    elBillForm = document.getElementById('bill-form');
}

// Fetch products from server
function loadProducts() {
    fetch('/api/products/')
        .then(res => res.json())
        .then(data => {
            products = data;
        })
        .catch(err => console.error("Error loading products:", err));
}

// Fetch customers from server
function loadCustomers() {
    fetch('/api/customers/')
        .then(res => res.json())
        .then(data => {
            customers = data;
        })
        .catch(err => console.error("Error loading customers:", err));
}

// Global Keyboard Shortcuts & Event Listeners
function setupEventListeners() {
    // Prevent default browser behavior for shortcuts
    window.addEventListener('keydown', (e) => {
        // Ctrl + S -> Save Bill
        if (e.ctrlKey && e.key.toLowerCase() === 's') {
            e.preventDefault();
            saveBill(false);
        }
        // Ctrl + P -> Print Bill
        if (e.ctrlKey && e.key.toLowerCase() === 'p') {
            e.preventDefault();
            saveBill(true);
        }
        // Ctrl + Alt + N or Ctrl + B -> Save & New Bill
        if (e.ctrlKey && e.altKey && e.key.toLowerCase() === 'n') {
            e.preventDefault();
            saveBill(false, true);
        }
    });

    // Product search suggestions navigation and input routing
    elProductSearch.addEventListener('input', (e) => {
        showProductSuggestions(e.target.value);
    });

    elProductSearch.addEventListener('keydown', (e) => {
        let items = elSuggestions.querySelectorAll('.suggestion-item');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (items.length > 0) {
                selectedProductIndex = (selectedProductIndex + 1) % items.length;
                highlightProductSuggestion(items);
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (items.length > 0) {
                selectedProductIndex = (selectedProductIndex - 1 + items.length) % items.length;
                highlightProductSuggestion(items);
            }
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (selectedProductIndex > -1 && items[selectedProductIndex]) {
                // Click highlighted item
                items[selectedProductIndex].click();
            } else {
                // Search by direct code or unique name match
                let val = elProductSearch.value.trim();
                let product = products.find(p => p.code.toLowerCase() === val.toLowerCase() || p.barcode === val);
                if (!product) {
                    // Try case-insensitive name match
                    product = products.find(p => p.name.toLowerCase() === val.toLowerCase());
                }
                if (product) {
                    selectProduct(product);
                } else if (items.length > 0) {
                    // Default select the first suggestion
                    items[0].click();
                } else {
                    alert("Product not found. Please create product in master.");
                }
            }
        } else if (e.key === 'Escape') {
            hideProductSuggestions();
        }
    });

    // Focus shifting
    elQty.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            elRate.focus();
            elRate.select();
        }
    });

    elRate.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addProductToBill();
        }
    });

    // Customer search autocomplete
    elCustomerSearch.addEventListener('input', (e) => {
        showCustomerSuggestions(e.target.value, 'name');
    });

    elCustomerSearch.addEventListener('keydown', (e) => {
        navigateCustomerSuggestions(e);
    });

    elCustomerPhone.addEventListener('input', (e) => {
        showCustomerSuggestions(e.target.value, 'phone');
    });

    elCustomerPhone.addEventListener('keydown', (e) => {
        navigateCustomerSuggestions(e);
    });

    // Recalculate totals on billing variables changed
    elDiscount.addEventListener('input', recalculateBill);
    elAmountPaid.addEventListener('input', recalculateBill);

    // Click outside to close suggestion dropdowns
    document.addEventListener('click', (e) => {
        if (!elProductSearch.contains(e.target) && !elSuggestions.contains(e.target)) {
            hideProductSuggestions();
        }
        if (!elCustomerSearch.contains(e.target) && !elCustomerPhone.contains(e.target) && !elCustomerSuggestions.contains(e.target)) {
            hideCustomerSuggestions();
        }
    });

    // Keyboard controls for the bill table (row navigation, F2 edit, Delete remove)
    setupTableKeyboardControls();
}

// Table row selections
let selectedTableIndex = -1;
function setupTableKeyboardControls() {
    document.addEventListener('keydown', (e) => {
        // If focusing inputs, don't trigger table shortcuts except special ones
        let inInput = ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName);
        if (inInput && editingRowId === null) return; 

        let rows = elBillTableBody.querySelectorAll('tr');
        if (rows.length === 0) return;

        if (e.key === 'ArrowDown' && !inInput) {
            e.preventDefault();
            selectedTableIndex = (selectedTableIndex + 1) % rows.length;
            highlightTableRow(rows);
        } else if (e.key === 'ArrowUp' && !inInput) {
            e.preventDefault();
            selectedTableIndex = (selectedTableIndex - 1 + rows.length) % rows.length;
            highlightTableRow(rows);
        } else if (e.key === 'F2') {
            e.preventDefault();
            if (selectedTableIndex > -1 && selectedTableIndex < rows.length) {
                startInlineEdit(selectedTableIndex);
            }
        } else if (e.key === 'Delete') {
            e.preventDefault();
            if (selectedTableIndex > -1 && selectedTableIndex < rows.length) {
                deleteRow(selectedTableIndex);
            }
        } else if (e.key === 'Escape' && editingRowId !== null) {
            e.preventDefault();
            cancelInlineEdit();
        }
    });
}

function highlightTableRow(rows) {
    rows.forEach((row, idx) => {
        if (idx === selectedTableIndex) {
            row.classList.add('selected-row');
            row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else {
            row.classList.remove('selected-row');
        }
    });
}

// Product Suggestion Dropdown
let activeSelectedProduct = null;
function showProductSuggestions(query) {
    elSuggestions.innerHTML = '';
    selectedProductIndex = -1;
    if (!query) {
        elSuggestions.classList.add('hidden');
        return;
    }

    let queryLower = query.toLowerCase();
    let matches = products.filter(p => 
        p.code.toLowerCase().includes(queryLower) || 
        p.name.toLowerCase().includes(queryLower) ||
        p.barcode.includes(queryLower)
    ).slice(0, 10); // cap suggestions to 10 rows

    if (matches.length === 0) {
        elSuggestions.classList.add('hidden');
        return;
    }

    matches.forEach((p, idx) => {
        let div = document.createElement('div');
        div.className = 'suggestion-item p-2 hover:bg-blue-600 hover:text-white cursor-pointer border-b border-gray-800 text-sm flex justify-between';
        div.innerHTML = `
            <span><strong>${p.code}</strong> - ${p.name}</span>
            <span>Rate: ₹${p.rate}</span>
        `;
        div.addEventListener('click', () => {
            selectProduct(p);
        });
        elSuggestions.appendChild(div);
    });

    elSuggestions.classList.remove('hidden');
}

function highlightProductSuggestion(items) {
    items.forEach((item, idx) => {
        if (idx === selectedProductIndex) {
            item.classList.add('bg-blue-600', 'text-white');
            item.scrollIntoView({ block: 'nearest' });
        } else {
            item.classList.remove('bg-blue-600', 'text-white');
        }
    });
}

function hideProductSuggestions() {
    elSuggestions.innerHTML = '';
    elSuggestions.classList.add('hidden');
    selectedProductIndex = -1;
}

function selectProduct(product) {
    activeSelectedProduct = product;
    elProductSearch.value = product.name;
    elQty.value = "1";
    elRate.value = product.rate;
    hideProductSuggestions();
    
    // Autofocus quantity and select its text
    elQty.focus();
    elQty.select();
}

// Add row to active bill
let lastInsertedProduct = null;
function addProductToBill() {
    if (!activeSelectedProduct) {
        alert("Please select a valid product first.");
        elProductSearch.focus();
        return;
    }

    let qty = parseFloat(elQty.value);
    let rate = parseFloat(elRate.value);
    
    if (isNaN(qty) || qty <= 0) {
        alert("Quantity must be a positive number.");
        elQty.focus();
        return;
    }
    
    if (isNaN(rate) || rate < 0) {
        alert("Rate cannot be negative.");
        elRate.focus();
        return;
    }

    let lineTotal = qty * rate;

    // Always add a new row for the product; do not merge duplicates.
    billItems.unshift({
        id: Date.now() + Math.random(), // local unique ID
        product_id: activeSelectedProduct.id,
        code: activeSelectedProduct.code,
        name: activeSelectedProduct.name,
        qty: qty,
        rate: rate,
        line_total: lineTotal,
        sr_no: nextSerial++
    });

    lastInsertedProduct = activeSelectedProduct;

    renderTable();
    recalculateBill();
    resetProductFields();

    // Focus product search and auto-fill previous product name with text pre-selected
    if (lastInsertedProduct) {
        elProductSearch.value = lastInsertedProduct.name;
        elProductSearch.focus();
        elProductSearch.select();
    }
}

function resetProductFields() {
    activeSelectedProduct = null;
    elProductSearch.value = '';
    elQty.value = '1';
    elRate.value = '0.00';
    hideProductSuggestions();
}

// Customer Autocomplete Handling
function showCustomerSuggestions(query, filterBy) {
    elCustomerSuggestions.innerHTML = '';
    selectedCustomerIndex = -1;
    if (!query) {
        elCustomerSuggestions.classList.add('hidden');
        return;
    }

    let queryLower = query.toLowerCase();
    let matches = customers.filter(c => {
        if (filterBy === 'name') {
            return c.name.toLowerCase().includes(queryLower);
        } else {
            return c.phone.includes(queryLower);
        }
    }).slice(0, 5);

    if (matches.length === 0) {
        elCustomerSuggestions.classList.add('hidden');
        return;
    }

    matches.forEach((c, idx) => {
        let div = document.createElement('div');
        div.className = 'cust-suggestion-item p-2 hover:bg-blue-600 hover:text-white cursor-pointer border-b border-gray-800 text-sm flex justify-between';
        div.innerHTML = `
            <span>${c.name || 'Walk-in'} (${c.phone || 'No phone'})</span>
            <span>Balance: ₹${c.balance}</span>
        `;
        div.addEventListener('click', () => {
            selectCustomer(c);
        });
        elCustomerSuggestions.appendChild(div);
    });

    elCustomerSuggestions.classList.remove('hidden');
}

function navigateCustomerSuggestions(e) {
    let items = elCustomerSuggestions.querySelectorAll('.cust-suggestion-item');
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (items.length > 0) {
            selectedCustomerIndex = (selectedCustomerIndex + 1) % items.length;
            highlightCustomerSuggestion(items);
        }
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (items.length > 0) {
            selectedCustomerIndex = (selectedCustomerIndex - 1 + items.length) % items.length;
            highlightCustomerSuggestion(items);
        }
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedCustomerIndex > -1 && items[selectedCustomerIndex]) {
            items[selectedCustomerIndex].click();
        } else {
            // Treat as fresh walk-in customer details
            hideCustomerSuggestions();
            // Move from Customer Name to Phone
            if (document.activeElement === elCustomerSearch) {
                elCustomerPhone.focus();
            } else if (document.activeElement === elCustomerPhone) {
                elProductSearch.focus();
            }
        }
    } else if (e.key === 'Escape') {
        hideCustomerSuggestions();
    }
}

function highlightCustomerSuggestion(items) {
    items.forEach((item, idx) => {
        if (idx === selectedCustomerIndex) {
            item.classList.add('bg-blue-600', 'text-white');
            item.scrollIntoView({ block: 'nearest' });
        } else {
            item.classList.remove('bg-blue-600', 'text-white');
        }
    });
}

function hideCustomerSuggestions() {
    elCustomerSuggestions.innerHTML = '';
    elCustomerSuggestions.classList.add('hidden');
    selectedCustomerIndex = -1;
}

function selectCustomer(cust) {
    activeCustomer = cust;
    elCustomerSearch.value = cust.name;
    elCustomerPhone.value = cust.phone;
    elOldBalance.textContent = parseFloat(cust.balance).toFixed(2);
    hideCustomerSuggestions();
    recalculateBill();
    elProductSearch.focus();
}

// Render dynamic table
function renderTable() {
    elBillTableBody.innerHTML = '';
    
    if (billItems.length === 0) {
        elSrNoNext.textContent = nextSerial;
        return;
    }

    billItems.forEach((item, idx) => {
        let isEditing = (editingRowId === item.id);
        let tr = document.createElement('tr');
        tr.className = 'border-b border-gray-800 text-sm hover:bg-gray-800 cursor-pointer';
        if (idx === selectedTableIndex) {
            tr.classList.add('selected-row');
        }

        if (isEditing) {
            tr.innerHTML = `
                <td class="p-2 text-center font-bold">${item.sr_no}</td>
                <td class="p-2">${item.name}</td>
                <td class="p-2"><input type="number" step="any" id="edit-qty-${item.id}" value="${item.qty}" class="w-20 p-1 text-right bg-black border border-gray-700 text-white rounded"></td>
                <td class="p-2"><input type="number" step="any" id="edit-rate-${item.id}" value="${item.rate}" class="w-20 p-1 text-right bg-black border border-gray-700 text-white rounded"></td>
                <td class="p-2 text-right">₹${item.line_total.toFixed(2)}</td>
            `;
            
            // Register inline edit events
            setTimeout(() => {
                let eq = document.getElementById(`edit-qty-${item.id}`);
                let er = document.getElementById(`edit-rate-${item.id}`);
                
                let handleInlineSubmit = (e) => {
                    if (e.key === 'Enter') {
                        saveInlineEdit(item.id, parseFloat(eq.value), parseFloat(er.value));
                    }
                };
                eq.addEventListener('keydown', handleInlineSubmit);
                er.addEventListener('keydown', handleInlineSubmit);
                eq.focus();
                eq.select();
            }, 10);
            
        } else {
            tr.innerHTML = `
                <td class="p-2 text-center font-bold">${item.sr_no}</td>
                <td class="p-2">${item.name}</td>
                <td class="p-2 text-right">${item.qty}</td>
                <td class="p-2 text-right">₹${item.rate.toFixed(2)}</td>
                <td class="p-2 text-right font-semibold">₹${item.line_total.toFixed(2)}</td>
            `;
        }

        // Row double-click to edit
        tr.addEventListener('dblclick', () => {
            startInlineEdit(idx);
        });

        elBillTableBody.appendChild(tr);
    });

    elSrNoNext.textContent = nextSerial;
    
    // Auto-scroll the table container to top to show newest entry
    let tableWrapper = document.getElementById('table-wrapper');
    if (tableWrapper) {
        tableWrapper.scrollTop = 0;
    }
}

// Inline Editing Row
function startInlineEdit(idx) {
    editingRowId = billItems[idx].id;
    renderTable();
}

function saveInlineEdit(id, newQty, newRate) {
    if (isNaN(newQty) || newQty <= 0) {
        alert("Quantity must be positive.");
        return;
    }
    if (isNaN(newRate) || newRate < 0) {
        alert("Rate cannot be negative.");
        return;
    }

    let idx = billItems.findIndex(item => item.id === id);
    if (idx > -1) {
        billItems[idx].qty = newQty;
        billItems[idx].rate = newRate;
        billItems[idx].line_total = newQty * newRate;
    }
    editingRowId = null;
    renderTable();
    recalculateBill();
    elProductSearch.focus();
}

function cancelInlineEdit() {
    editingRowId = null;
    renderTable();
    elProductSearch.focus();
}

function deleteRow(idx) {
    billItems.splice(idx, 1);
    selectedTableIndex = Math.min(selectedTableIndex, billItems.length - 1);
    renderTable();
    recalculateBill();
}

// Calculations
function recalculateBill() {
    let gross = 0;
    billItems.forEach(item => {
        gross += item.line_total;
    });

    let discount = parseFloat(elDiscount.value);
    if (isNaN(discount) || discount < 0) discount = 0;

    let net = Math.max(0, gross - discount);
    
    let paid = parseFloat(elAmountPaid.value);
    if (isNaN(paid) || paid < 0) paid = 0;

    let pending = net - paid;
    let oldBal = parseFloat(elOldBalance.textContent);
    if (isNaN(oldBal)) oldBal = 0;

    let finalBal = oldBal + pending;

    elGrossTotal.textContent = gross.toFixed(2);
    elNetTotal.textContent = net.toFixed(2);
    elPendingAmount.textContent = pending.toFixed(2);
    elFinalBalance.textContent = finalBal.toFixed(2);
}

// Save Bill Draft Payload to Server
function saveBill(triggerPrint = false, stayOnPage = false) {
    if (billItems.length === 0) {
        alert("Cannot save an empty bill. Please add items.");
        elProductSearch.focus();
        return;
    }

    // Build Payload
    let payload = {
        customer_name: elCustomerSearch.value.trim(),
        customer_phone: elCustomerPhone.value.trim(),
        gross_total: parseFloat(elGrossTotal.textContent),
        discount: parseFloat(elDiscount.value) || 0,
        net_total: parseFloat(elNetTotal.textContent),
        amount_paid: parseFloat(elAmountPaid.value) || 0,
        pending_amount: parseFloat(elPendingAmount.textContent),
        old_balance: parseFloat(elOldBalance.textContent),
        final_balance: parseFloat(elFinalBalance.textContent),
        items: billItems.map(item => ({
            product_id: item.product_id,
            quantity: item.qty,
            rate: item.rate,
            line_total: item.line_total,
            sr_no: item.sr_no
        }))
    };

    let csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    fetch('/billing/save/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            // Trigger browser print
            if (triggerPrint) {
                let printUrl = `/billing/print/${data.bill_id}/`;
                let printWindow = window.open(printUrl, '_blank', 'width=800,height=600');
                
                // Wait for printer preview trigger inside loaded print window, then reload/redirect
                printWindow.onload = () => {
                    printWindow.print();
                    if (!stayOnPage) {
                        window.location.reload();
                    }
                };
            } else {
                alert(`Bill saved successfully! Bill No: ${data.bill_number}`);
                if (!stayOnPage) {
                    window.location.reload();
                }
            }

            if (stayOnPage) {
                // If staying on page, we just reset the draft items and refresh product/customer codes
                billItems = [];
                activeCustomer = null;
                elCustomerSearch.value = '';
                elCustomerPhone.value = '';
                elOldBalance.textContent = '0.00';
                elDiscount.value = '0.00';
                elAmountPaid.value = '0.00';
                renderTable();
                recalculateBill();
                resetProductFields();
                loadProducts();
                loadCustomers();
                // update next bill number label in DOM if returned
                if(data.next_bill_number) {
                    let elBillNo = document.getElementById('bill-number-display');
                    if(elBillNo) elBillNo.textContent = data.next_bill_number;
                }
            }
        } else {
            alert("Error saving bill: " + data.message);
        }
    })
    .catch(err => {
        console.error("Save Error:", err);
        alert("Failed to submit bill. Check server logs.");
    });
}
