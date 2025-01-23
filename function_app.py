import logging
import json
import os
import mimetypes
import azure.functions as func
from utils.helpers import FunctionalUtils
from src.function_main import (
    create_and_send_quote,
    get_customer_or_carrier_contacts,
    handle_send_quote_request,
    handle_send_dispatch_email,
    handle_send_quote,
    handle_send_invoice
)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="ping", methods=['GET'])
async def ping(req: func.HttpRequest) -> func.HttpResponse:
    
    logging.info('Ping request received.')
    return func.HttpResponse("Service is up", status_code=200)


@app.route(route="quote/form", methods=['GET'])
async def get_quote_form(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    try:
        params = {
            "carrierID": req.params.get('carrierID'),
            "jobID": req.params.get('jobID'),
            "carriername": req.params.get('carriername')
        }
        filepath = os.path.join(context.function_directory, "src/static/create_quote.html")
        html_content = FunctionalUtils.render_html_template(filepath, params)

        mimetype = mimetypes.guess_type(filepath)
        return func.HttpResponse(html_content, mimetype=mimetype[0])
    except Exception:
        return func.HttpResponse("Internal Server Error", status_code=500)


@app.route(route="quote/create", methods=['POST'])
async def create_quote(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()
        response = await create_and_send_quote(data)
        return func.HttpResponse(json.dumps(response), mimetype="application/json",status_code=200)
    except Exception as e:
        logging.error(f"Error creating the quote: {e}")
        error_data = {"error": str(e)}
        return func.HttpResponse(json.dumps(error_data), mimetype="application/json", status_code=500)


@app.route(route="contacts", methods=['GET'])
async def fetch_contacts(req: func.HttpRequest) -> func.HttpResponse:
    try:
        email_type = req.params.get("email_type")
        carrier_id = req.params.get("carrierid")
        customer_id = req.params.get("customerid")

        response = await get_customer_or_carrier_contacts(email_type=email_type,carrier_id=carrier_id, customer_id=customer_id)
        if response['status'] == "success":
            emails = response['emails']
            return func.HttpResponse(json.dumps(emails), mimetype="application/json", status_code=200)
        else:
            return func.HttpResponse(json.dumps(response))

    except Exception as e:
        logging.error(f"Error fetching carrier contacts: {e}")
        return func.HttpResponse(json.dumps({"status":"failed","message":"Failed to get Contact", "error":str(e)}), status_code=500)


@app.route(route="email/form", methods=['GET'])
async def get_email_form(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    params = {
        "dealid": req.params.get('DealID', ''),
        "quoteid": req.params.get('QuoteID', ''),
        "carrierid": req.params.get('CarrierID', ''),
        "customerid": req.params.get('CustomerID', ''),
        "email_type": req.params.get('email_type'),
        "ToName": req.params.get('toname', ''),
        "invoice_price": req.params.get('invoice_price', '')
    }
    filepath = os.path.join(context.function_directory, "src/static/email_form.html")
    try:
        html_content = FunctionalUtils.render_html_template(filepath, params)
        return func.HttpResponse(html_content, mimetype="text/html")
    except Exception:
        return func.HttpResponse("Internal Server Error", status_code=500)


@app.route(route="static", methods=["GET"])
async def serve_static_file(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    """
    Serve static files (e.g., CSS, JS) from the 'static' directory.
    """
    file_name = req.params.get("filename")

    static_dir = os.path.join(os.getcwd(), "src/static")
    # if os.path.isfile(full_path):
    if file_name.endswith(".css"):
        full_path = os.path.join(static_dir, f"css/{file_name}") 
        mime_type = "text/css"
    elif file_name.endswith(".js"):
        full_path = os.path.join(static_dir, f"js/{file_name}") 
        mime_type = "application/javascript"
    else:
        mime_type = "application/octet-stream"

    try:
        with open(full_path, "rb") as file:
            return func.HttpResponse(file.read(), mimetype=mime_type)
        
    except Exception as e:
        return func.HttpResponse("File not found", status_code=404)


@app.route(route="email/send",methods=['POST'])
async def send_emails(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    try:
        email_type = req.params.get('type')
        data = req.get_json()
        # required parameters
        deal_id = data.get("dealid")
        quote_id = data.get("quoteid")
        email_address = data.get("email")
        carrier_id = data.get("carrierid")
        receiver_name = data.get("receivername")
        customer_price_excl_tax = data.get("customerprice_excl_tax")
          
        email_params = {
            "html_content": None,
            "subject": None,
            "to": {
                "user_name": data.get("receivername"),
                "email": data.get("email")
            },
            "zoho_deal_id": data.get("dealid"),
            "attachment_ids": None
        }
        
        handlers = {
            "QuoteRequest": (handle_send_quote_request, ["dealid", "quoteid", "email_params"]),
            "Dispatch": (handle_send_dispatch_email, ["dealid", "quoteid", "email_params"]),
            "SendQuote": (handle_send_quote, ["dealid", "quoteid", "email_params", "customerprice_excl_tax"]),
            "Invoice": (handle_send_invoice, ["dealid", "quoteid", "email_params","invoice_amount"])
        }

        # Get the handler and expected arguments
        handler_info = handlers.get(email_type)
        if not handler_info:
            raise ValueError("Invalid email type provided.")
        
        handler, arg_keys = handler_info
    
        args = [email_params if key == "email_params" else data.get(key) for key in arg_keys]

        response = await handler(*args)

        return func.HttpResponse(json.dumps(response), mimetype="application/json", status_code=200)
     
    except Exception as e:
        logging.exception("Error in Send Email endpoint")
        return func.HttpResponse(json.dumps({"status":"failed","message":"Internal Server Error","error":str(e)}))