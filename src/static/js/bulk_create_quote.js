let quoteCounter = 0;
let expandedQuoteId = null;
let orderDataMap = {}; // Stores order data for quick lookup

function parseOrderData(pcordernames) {
    orderDataMap = {}; // Reset the map
    if (pcordernames) {
        const orders = pcordernames.split(",");
        orders.forEach(order => {
            const [potentialID, dealID, orderID] = order.split("-");
            if (potentialID && dealID && orderID) {
                orderDataMap[orderID.trim()] = {
                    potentialID: potentialID.trim(),
                    dealID: dealID.trim()
                };
            }
        });
    }
}
function createQuoteForm() {
    quoteCounter++;
    const quoteForm = document.createElement('div');
    quoteForm.className = 'quote-form';
    quoteForm.dataset.quoteId = quoteCounter;
    const pcordernames = document.body.dataset.pcordernames;
    console.log("pcordernames", pcordernames);
    const chevronSvg = `<svg class="chevron" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>`;
    // Split and generate order options
    parseOrderData(pcordernames); // Parse the order data

    let orderOptions = `<option value="">Select Order ID</option>`;
    Object.keys(orderDataMap).forEach(orderID => {
        orderOptions += `<option value="${orderID}">${orderID}</option>`;
    });
    quoteForm.innerHTML = `
    <div class="quote-header" onclick="toggleQuote(${quoteCounter})">
        <span class="quote-number">
            ${chevronSvg}
            Quote #${quoteCounter}
            <span class="quote-amount"></span>
        </span>
        ${quoteCounter > 1 ? `<button type="button" class="remove-quote" onclick="removeQuoteForm(${quoteCounter}, event)">×</button>` : ''}
    </div>
    <div class="quote-content">
        <!-- Order ID Field -->
        <label for="orderId-${quoteCounter}">Order ID</label>
        <div class="order-select">
            <select id="orderId-${quoteCounter}" name="orderId">
                ${orderOptions}
            </select>
        </div>

        <!-- Estimated Amount Field -->
        <label for="estimatedAmount-${quoteCounter}">Estimated Amount: (Per Vehicle)</label>
        <div class="pricing-input">
            <select id="priceunit-${quoteCounter}" name="priceunit" onchange="updateQuoteAmount(${quoteCounter})">
                <option value="CAD">CAD</option>
                <option value="USD">USD</option>
            </select>
            <input type="text" id="estimatedAmount-${quoteCounter}" 
                   placeholder="Enter Estimated Amount"
                   onchange="updateQuoteAmount(${quoteCounter})"
                   onkeyup="updateQuoteAmount(${quoteCounter})">
        </div>
        <!--- Customer Price Field -->
        <label for="customerPrice-${quoteCounter}">Customer Price (Excl. Tax):</label>
        <input type="text" id="customerPrice-${quoteCounter}" placeholder="Enter Customer Price">
        
        <!-- Estimated Pickup Days -->
        <label for="pickupMin-${quoteCounter}">Estimated Pickup (Days):</label>
        <div class="range-input">
            <input type="text" id="pickupMin-${quoteCounter}" placeholder="Min (days)">
            <input type="text" id="pickupMax-${quoteCounter}" placeholder="Max (days)">
        </div>
        
        <!-- Delivery Date Days -->
        <label for="deliveryMin-${quoteCounter}">Delivery Date (Days):</label>
        <div class="range-input">
            <input type="text" id="deliveryMin-${quoteCounter}" placeholder="Min (days)">
            <input type="text" id="deliveryMax-${quoteCounter}" placeholder="Max (days)">
        </div>
    </div>
`;

    return quoteForm;
}

function toggleQuote(quoteId) {
    const allQuotes = document.querySelectorAll('.quote-form');
    allQuotes.forEach(quote => {
        if (parseInt(quote.dataset.quoteId) !== quoteId) {
            quote.classList.add('collapsed');
        }
    });

    const currentQuote = document.querySelector(`.quote-form[data-quote-id="${quoteId}"]`);
    currentQuote.classList.toggle('collapsed');
    expandedQuoteId = currentQuote.classList.contains('collapsed') ? null : quoteId;
}

function updateQuoteAmount(quoteId) {
    const amount = document.getElementById(`estimatedAmount-${quoteId}`).value;
    const currency = document.getElementById(`priceunit-${quoteId}`).value;
    const amountSpan = document.querySelector(`.quote-form[data-quote-id="${quoteId}"] .quote-amount`);
    
    if (amount) {
        amountSpan.textContent = `(${currency === 'CAD' ? 'CAD' : 'USD'} ${amount})`;
    } else {
        amountSpan.textContent = '';
    }
}

function addQuoteForm() {
    const quotesList = document.getElementById('quotes-list');
    const newQuoteForm = createQuoteForm();
    quotesList.appendChild(newQuoteForm);

    // Only collapse other quotes, keep the new one expanded
    const allQuotes = document.querySelectorAll('.quote-form');
    allQuotes.forEach(quote => {
        if (parseInt(quote.dataset.quoteId) !== quoteCounter) {
            quote.classList.add('collapsed');
        }
    });

    expandedQuoteId = quoteCounter;
}

function removeQuoteForm(quoteId, event) {
    event.stopPropagation();
    const quoteForm = document.querySelector(`.quote-form[data-quote-id="${quoteId}"]`);
    if (quoteForm) {
        quoteForm.remove();
        if (expandedQuoteId === quoteId) {
            expandedQuoteId = null;
        }
    }
}

function getFormattedRange(min, max) {
    const isValidNumber = (value) => value !== "" && !isNaN(value);
    
    if (!isValidNumber(min) && !isValidNumber(max)) {
        return "";
    }
    if (isValidNumber(min) && isValidNumber(max)) {
        return `${min} - ${max} Business Days`;
    }
    if (isValidNumber(min)) {
        return `${min} Business Days`;
    }
    if (isValidNumber(max)) {
        return `${max} Business Days`;
    }
    return "";
}

async function submitAllQuotes() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.style.display = 'block';

    const quoteForms = document.querySelectorAll('.quote-form');
    const carrierID = document.body.dataset.carrierid;
    const jobID = document.body.dataset.jobid;
    // const potentialID = document.body.dataset.potentialid;
    const carrierName = document.querySelector('h2[data-carriername]')?.dataset.carriername;

    const quotes = Array.from(quoteForms).map(form => {
        const quoteId = form.dataset.quoteId;
        const estimatedAmount = document.getElementById(`estimatedAmount-${quoteId}`).value;
        const currency_unit = document.getElementById(`priceunit-${quoteId}`).value;
        const pickupMin = document.getElementById(`pickupMin-${quoteId}`).value;
        const pickupMax = document.getElementById(`pickupMax-${quoteId}`).value;
        const deliveryMin = document.getElementById(`deliveryMin-${quoteId}`).value;
        const deliveryMax = document.getElementById(`deliveryMax-${quoteId}`).value;
        const ordername = document.getElementById(`orderId-${quoteId}`).value;
        const customerprice_excl_tax = document.getElementById(`customerPrice-${quoteId}`).value;
        const carrierID = document.body.dataset.carrierid;
        console.log( {
            Estimated_Amount: estimatedAmount,
            EstimatedPickupRange: getFormattedRange(pickupMin, pickupMax),
            DeliveryDate: getFormattedRange(deliveryMin, deliveryMax),
            CarrierID: carrierID,
            DealID: orderDataMap[ordername].dealID,
            currency: currency_unit,
            carrierName: carrierName,
            PotentialID: orderDataMap[ordername].potentialID,

            

        });
        return {
            Estimated_Amount: estimatedAmount,
            EstimatedPickupRange: getFormattedRange(pickupMin, pickupMax),
            DeliveryDate: getFormattedRange(deliveryMin, deliveryMax),
            CarrierID: carrierID,
            DealID: orderDataMap[ordername].dealID,
            Currency: currency_unit,
            CarrierName: carrierName,
            PotentialID: orderDataMap[ordername].potentialID,
            CustomerPriceExclTax: customerprice_excl_tax

        };
    });

    if (!quotes.some(quote => quote.Estimated_Amount)) {
        alert("Please fill out at least one quote amount.");
        loadingSpinner.style.display = 'none';
        return;
    }

    try {
        const responses = await Promise.all(quotes.map(quote =>
            fetch("/api/quote/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(quote)
            }).then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.error || "Unknown error occurred");
                    });
                }
                return response.json();
            })
        ));

        const lastResponse = responses[responses.length - 1];
        if (lastResponse.status == "success") {
            Swal.fire({
                icon: "success",
                title: "Yo!",
                toast: true,  // Makes it smaller
                position: "top-end", // Moves to top-right
                showConfirmButton: false,
                timer: 2000, // Auto-closes in 2 sec
                timerProgressBar: true,
                text: "All Quote has been Created!",
                confirmButtonText: "OK"
            }).then(() => {
                window.opener.location.href = data.redirect_url;
                window.close();
            });
            
        }
    } catch (error) {
        console.error("Error:", error);
        Swal.fire({
            icon: "error",
            title: "Failed to Send Email",
            text:error.message
        });
    } finally {
        loadingSpinner.style.display = 'none';
    }
}

window.addEventListener('DOMContentLoaded', () => {
    addQuoteForm();
});