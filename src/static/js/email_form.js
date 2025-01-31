// Ensure the token and carrierid are passed correctly from the HTML attributes

const dealid = document.body.getAttribute('data-dealid'); // Get carrier ID from data attribute
const carrierid = document.body.getAttribute('data-carrierid'); // Get carrier ID from data attribute
const emailDropdown = document.getElementById("email");
const emailtype = document.body.getAttribute('data-emailtype');
const formTitle = document.getElementById("form-title");
const submit_button = document.getElementById('submit-button');
const customerid = document.body.getAttribute('data-customerid');
const quoteid = document.body.getAttribute('data-quoteid');
const toname = document.body.getAttribute('data-toname');
const invoiced_amount = document.body.getAttribute('data-invoicedprice');
const potentialID = document.body.getAttribute('data-potentialid');

if (emailtype == "Dispatch") {
        formTitle.textContent = "Dispatch Form";
        submit_button.textContent = "Send Dispatch";

    }else if (emailtype == "QuoteRequest") {
        formTitle.textContent = "Quote Request Form";
        submit_button.textContent = "Send Quote Request";

    }else if (emailtype == "SendQuote") {
        const inputField = document.getElementById("customerprice");
        const customerpricelabel = document.getElementById("customerpricelabel");
        inputField.required = true;
        formTitle.textContent = "Send Quote Form";
        submit_button.textContent = "Send Quote";
        inputField.type = "text";
        customerpricelabel.textContent = "Customer Price (Excl. Tax):";

    }else if (emailtype == "SendInvoice") {
        formTitle.textContent == "Invoice Prep Form";
        submit_button.textContent = "Send Invoice";
        document.getElementById('invoiceprice').hidden = false;
    }
emailDropdown.disabled = true;

// Function to fetch customer contacts
async function getCarrierContacts(carrierid, customerid) {
    console.log(carrierid);
    console.log(customerid);
    var API_URL = ''
    if (carrierid || carrierid !='') {
        API_URL = `/api/contacts?carrierid=${carrierid}&email_type=${emailtype}`;
    }else{
        API_URL = `/api/contacts?customerid=${customerid}&email_type=${emailtype}`;
    }
    const loadingSpinner = document.getElementById("loadingSpinner");
    loadingSpinner.style.display = "block"; // Show loading spinner

    try {
        const response = await fetch(API_URL, {
            method: 'GET',
        });

        if (!response.ok) {
            throw new Error(`Error: ${response.statusText}`);
        }

        const data = await response.json();
        return data;

    } catch (error) {
        console.error("Error getting customer contacts: ", error);
        return { message: "Error getting customer contacts", error: error.message };
    }
}

// Fetch the contacts using the available token and carrierid
getCarrierContacts(carrierid, customerid)
    .then(data => {
        if (data) {
            loadingSpinner.style.display = "none"; // Hide loading spinner
            const emailDropdown = document.getElementById("email");
            emailDropdown.disabled = false;  // Enable the dropdown
            // Populate the email dropdown
            Object.entries(data).forEach(([email, name]) => {
                const option = document.createElement("option");
                option.value = email;
                option.textContent = `${email} - ${name}`;
                emailDropdown.appendChild(option);
            });
        } else {
            console.error("Invalid data format or no contacts found.");
        }
    })
    .catch(error => {
        console.error("Error:", error);
    });
// Modify the SendDispatchEmail function to prevent the page reload
document.getElementById('dispatchForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent default form submission (page reload)
    SendEmail();
    
    
});
function SendEmail() {
    const loadingSpinner = document.getElementById("loadingSpinner");
    loadingSpinner.style.display = "block"; // Show loading spinner

    const email = document.getElementById("email").value;
    const manualEmail = document.getElementById("manualEmail").value;
    const customerprice = document.getElementById("customerprice").value;

    const data = {
        Deal_ID: dealid, // Make sure deal_id is defined
        Carrier_ID: carrierid, // Make sure carrierid is defined
        ToEmail: email || manualEmail,
        Quote_ID: quoteid,
        ToName : toname,
        CustomerPrice_ExclTax : customerprice,
        Invoiced_Amount : invoiced_amount,
        potentialID : potentialID

    };

    fetch(`/api/email/send?type=${emailtype}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json()) // Parse the response as JSON
    .then(data => {
        loadingSpinner.style.display = "none"; // Hide loading spinner
        if (data.status == "success") {
            alert("Email sent successfully!"); // Assuming 'success' field is part of the response data
            window.opener.location.href = data.redirect_url;
            window.close();
        } else {
            alert("Failed to send email.");
        }

    })
    .catch(error => {
        loadingSpinner.style.display = "none"; // Hide loading spinner
        console.error("Error sending email:", error);
        alert("An error occurred while sending the dispatch email. "+ error);
    });
}

