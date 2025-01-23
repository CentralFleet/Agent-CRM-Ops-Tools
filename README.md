# Zoho-Ops-Tools 

**Zoho-Ops-Tools** is a serverless application designed to streamline business operations by interacting with Zoho CRM and other external services. These tools empower active agents in Zoho to manage operations such as creating quotes directly using form, sending emails, and handling dispatch requests efficiently.


---

## Endpoints

### 1. Health Check
- **Route:** `GET /ping`
- **Description:** Checks the availability of the service.
- **Response:** 
  ```json
  {
    "message": "Service is up"
  }

### 2. Fetch Quote form
- **URL**: `/api/quote/form`
- **Method**: `GET`
- **Query Parameters**:
  - `carrierID` (String, Required): Unique ID of the carrier.
  - `jobID` (String, Required): Unique ID of the job.
  - `carriername` (String, Optional): Name of the carrier.

### **Response**
- **Status Code**: `200 OK`
- **Content-Type**: `text/html`
- **Body**: HTML form rendered for creating a quote.

## 2. Create Quote

### **Request**
- **URL**: `/api/quote/create`
- **Method**: `POST`
- **Request Body (JSON)**:
  ```json
  {
    "carrierID": "12345",
    "jobID": "98765",
    "carriername": "FleetExpress",
    "pickup": "New York, NY",
    "dropoff": "Los Angeles, CA",
    "price": "1500",
    "notes": "Handle with care"
  }
  ```

### **Response**
- **Status Code**: `200 OK`
- **Content-Type**: `application/json`
- **Body**: JSON response indicating the success or failure of the quote creation.

## 3. Fetch Email Form

### **Request**
- **URL**: `/api/email/form`
- **Method**: `GET`
- **Query Parameters**:
  - `carrierID` (String, Required): Unique ID of the carrier.
  - `jobID` (String, Required): Unique ID of the job.

### **Response**
- **Status Code**: `200 OK`
- **Content-Type**: `text/html`
- **Body**: HTML form rendered for sending an email.

## 4. Send Email

### **Request**
- **URL**: `/api/email/send`
- **Method**: `POST`
- **Request Body (JSON)**:
  ```json
  {
    "Deal_ID": "DEAL12345",            // Unique ID of the deal
    "Carrier_ID": "CARRIER67890",      // Unique ID of the carrier
    "ToEmail": "example@domain.com",   // Recipient's email address
    "Quote_ID": "QUOTE001234",         // Unique ID of the quote
    "ToName": "John Doe",              // Recipient's name
    "CustomerPrice_ExclTax": 1500.00, 
    "Invoiced_Amount": 1600.00         
  }
  ```
## **Response**
- **Status Code**: `200 OK`
- **Content-Type**: `application/json`
- **Body**: JSON response indicating the success or failure of the email sending operation.

## 5. Static Files

### **Request**
- **URL**: `/api/static`
- **Method**: `GET`

### **Response**
- **Status Code**: `200 OK`
- **Content-Type**: `text/html`
- **Body**: HTML content of the requested static file.

