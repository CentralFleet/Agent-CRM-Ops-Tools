function submitQuote() {
    const loadingSpinner = document.getElementById('loadingSpinner');
    loadingSpinner.style.display = 'block'; // Show loading spinner

    let estimatedAmount = document.getElementById('estimatedAmount').value;
    let pickupMin = document.getElementById('pickupMin').value;
    let pickupMax = document.getElementById('pickupMax').value;
    let deliveryMin = document.getElementById('deliveryMin').value;
    let deliveryMax = document.getElementById('deliveryMax').value;
    var currency_unit = document.getElementById("priceunit").value;
    const carrierName = document.querySelector('h2[data-carriername]').dataset.carriername;
    let customerprice_excl_tax = document.getElementById('customerPrice').value;

    let estimated_pickup = "";
    let DeliveryDate = "";

    if (!estimatedAmount) {
        alert("Please fill out all fields.");
        loadingSpinner.style.display = 'none'; // Hide loading spinner
        return;
    }


    // Helper function to check if a value is a valid number
    const isValidNumber = (value) => value !== "" && !isNaN(value);

    // Handle pickup range
    if (!isValidNumber(pickupMin) && !isValidNumber(pickupMax)) {
        estimated_pickup = "";
        pickupMin = "";
        pickupMax = "";
    } else if (isValidNumber(pickupMin) && isValidNumber(pickupMax)) {
        pickupMin = Number(pickupMin);
        pickupMax = Number(pickupMax);
        estimated_pickup = `${pickupMin} - ${pickupMax} Business Days`;
    } else if (isValidNumber(pickupMin) && !isValidNumber(pickupMax)) {
        pickupMin = Number(pickupMin);
        pickupMax = pickupMin + 2; // Add two days to the minimum pickup days
        estimated_pickup = `${pickupMin} Business Days`;
    } else if (!isValidNumber(pickupMin) && isValidNumber(pickupMax)) {
        pickupMax = Number(pickupMax);
        pickupMin = pickupMax - 2; // Subtract two days from the maximum pickup days
        estimated_pickup = `${pickupMax} Business Days`;
    }

    // Handle delivery range
    if (!isValidNumber(deliveryMin) && !isValidNumber(deliveryMax)) {
        DeliveryDate = "";
        deliveryMin = "";
        deliveryMax = "";
    } else if (isValidNumber(deliveryMin) && isValidNumber(deliveryMax)) {
        deliveryMin = Number(deliveryMin);
        deliveryMax = Number(deliveryMax);
        DeliveryDate = `${deliveryMin} - ${deliveryMax} Business Days`;
    } else if (isValidNumber(deliveryMin) && !isValidNumber(deliveryMax)) {
        deliveryMin = Number(deliveryMin);
        deliveryMax = deliveryMin + 2; // Add two days to the minimum delivery days
        DeliveryDate = `${deliveryMin} Business Days`;
    } else if (!isValidNumber(deliveryMin) && isValidNumber(deliveryMax)) {
        deliveryMax = Number(deliveryMax);
        deliveryMin = deliveryMax - 2; // Subtract two days from the maximum delivery days
        DeliveryDate = `${deliveryMax} Business Days`;
    }



    const carrierID = document.body.dataset.carrierid;
    const jobID = document.body.dataset.jobid;
    const potentialID = document.body.dataset.potentialid;

    console.log("Customer Price is ", customerprice_excl_tax);
    const data = {
        Estimated_Amount: estimatedAmount,
        EstimatedPickupRange: estimated_pickup,
        DeliveryDate: DeliveryDate,
        CarrierID: carrierID,
        DealID: jobID,
        Currency: currency_unit,
        CarrierName: carrierName,
        PotentialID: potentialID,
        CustomerPriceExclTax: customerprice_excl_tax
    };

    fetch("/api/quote/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errorData => {
                throw new Error(errorData.error || "Unknown error occurred");
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.message) {
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
    })
    .catch(error => {
        console.error("Error:", error);
        Swal.fire({
            icon: "error",
            title: "Failed to Send Email",
            text: error.message
        });   
    })
    .finally(() => {
        loadingSpinner.style.display = 'none'; // Hide loading spinner after completion
    });
}