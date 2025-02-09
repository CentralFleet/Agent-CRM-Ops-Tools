from pyzohocrm import ZohoApi,TokenManager
import os
from utils.helpers import EmailUtils, LoggingUtils, FunctionalUtils
from utils.models import *
import requests
import json
import asyncio
logger = LoggingUtils.get_logger(__name__)

TEMP_DIR = "/tmp"

TOKEN_INSTANCE =  TokenManager(
                                domain_name="Canada",
                                refresh_token=os.getenv("REFRESH_TOKEN"),
                                client_id=os.getenv("CLIENT_ZOHO_ID"),
                                client_secret=os.getenv("CLIENT_ZOHO_SECRET"),
                                grant_type="refresh_token",
                                token_dir=TEMP_DIR
                                )

ZOHO_API = ZohoApi(base_url="https://www.zohoapis.ca/crm/v2")


async def create_and_send_quote(data):
    token = TOKEN_INSTANCE.get_access_token()
    logger.info(f"Triggered `send_quote_to_crm_and_sql` with data: {data}")
    
    ## Fetch Deal Details
    deal_info = ZOHO_API.read_record(moduleName="Deals",id=data.get('DealID'),token=token).json()
    deal_details = deal_info.get('data', [{}])[0]

    def send_quote_to_crm():
        new_quote = Quotes(
            Estimated_Amount = data.get('Estimated_Amount'),
            Delivery_Date_Range = data.get('DeliveryDate'),
            Dropoff_Location = deal_details.get('Drop_off_Location'),
            Pickup_Location  = deal_details.get('PickupLocation'),
            pickup_date_range = data.get('EstimatedPickupRange'),
            VendorID = data.get('CarrierID'),
            DealID = data.get('DealID'),
            Name = data.get("CarrierName") + " - " + deal_details.get("Deal_Name"),
            CreateDate = datetime.now().strftime("%Y-%m-%d"),
            Customer_Price_Excl_Tax = data.get('CustomerPriceExclTax')
        )
        ## send Quote details to the CRM
        create_quote_response = ZOHO_API.create_record(moduleName="Transport_Offers",data={"data":[dict(new_quote)]},token=token)
        logger.info(f"CREATE QUOTE RESPONSE : {create_quote_response.json()}")
        return create_quote_response.json()

    def send_quote_to_sql(quote_id):
            url = "https://lead-quote-service.azurewebsites.net/api/v1/store-quotes?"  ## forward request to transport service to add quote into db
            new_sql_quote = {
                "QuotationRequestID": quote_id,
                "CarrierID":  data.get('CarrierID'),
                "CarrierName": data.get("CarrierName"),
                "DropoffLocation":deal_details.get('Drop_off_Location'),
                "PickupLocation": deal_details.get('PickupLocation'),
                "EstimatedPickupTime": data.get('EstimatedPickupRange'),
                "EstimatedDropoffTime": data.get('DeliveryDate'),
                "Estimated_Amount": data.get('Estimated_Amount'),
                "Pickup_City":  deal_details.get("Pickup_City"),
                "Dropoff_City": deal_details.get("Dropoff_City"),
                "Tax_Province": deal_details.get("Tax_Province"),
                "CustomerPrice_excl_tax": data.get('CustomerPrice_ExclTax')
            }
            sqlquote_response = requests.post(url, json=new_sql_quote)
            return sqlquote_response.json()

    quote_crm_response = send_quote_to_crm()
    quote_id = quote_crm_response['data'][0]['details']['id']
    sql_response = send_quote_to_sql(quote_id=quote_id)
    if deal_details.get('Stage') in ["Send Quote to Customer", "Shop for Quotes"]:
        ZOHO_API.update_record(moduleName="Deals",id=data.get('DealID'),token=token,data={"data":[{"Stage":"Send Quote to Customer","Order_Status":"Quote Ready"}]})

    ZOHO_API.update_record(moduleName="Potential_Carrier",id=data.get('PotentialID'),token=token,data={"data":[{"Progress_Status":"Quote Received",
                                                                                                                "Est_Delivery_Date":data.get('DeliveryDate'),
                                                                                                                "Est_Pickup_Date":data.get('EstimatedPickupRange'),
                                                                                                                "Estimated_Amount":data.get('Estimated_Amount')}]} )
    return {
            "status":"success",
            "quote_create_response":{
                "crm_response":quote_crm_response,
                "sql_response":sql_response
            },
        "message": "Quote created successfully", 
        "redirect_url": f"https://crm.zohocloud.ca/crm/org110000402423/tab/Deals/{data.get('DealID')}"
    }


async def get_customer_or_carrier_contacts(email_type : str, carrier_id: str = None, customer_id : str = None):
    logger.info(f"Triggered `get_contacts` for email type: {email_type} and {carrier_id} and {customer_id}")
    try:
        token = TOKEN_INSTANCE.get_access_token()

        email_collection = {}
        if email_type in ("Dispatch", "QuoteRequest", "BulkQuoteRequest","RequestOrderUpdate"):
            carrier_contacts = ZOHO_API.fetch_related_list(moduleName="Vendors",record_id=carrier_id,token=token,name="Contact")
            logger.info(carrier_contacts.json())
            if carrier_contacts.status_code == 200:
                for contact in carrier_contacts.json()['data']:
                    email_collection[contact['Email']] = contact['Last_Name']


        elif email_type in  ("SendQuote","SendInvoice","OrderConfirmation","SendOrderUpdate"):
            contacts_resp_v2 = ZOHO_API.fetch_related_list(moduleName="Accounts",record_id=customer_id,token=token,name="DealerContact")
            if contacts_resp_v2.status_code == 204:
                contacts_resp_v1 = ZOHO_API.fetch_related_list(moduleName="Accounts",record_id=customer_id,token=token,name="Contacts12")
                logger.info(contacts_resp_v1.json())
                if contacts_resp_v1:
                    for contact in contacts_resp_v1.json().get('data', [{}]):
                        contact_details = ZOHO_API.read_record(moduleName="Contacts",id=contact['Company']['id'],token=token).json().get('data', [{}])[0]
                        email_collection[contact_details['Email']] = contact_details['Last_Name']

                else:
                    return {"status":"failed","message":"No Email Found","error":str(e)}
            else:
                for contact in contacts_resp_v2.json().get('data', [{}]):
                    email_collection[contact['Email']] = contact['Last_Name']

        logger.info(f"Contact Email for requested Customer or Carrier is {email_collection}")

        return {"status":"success","message":"successfully fetched emails","emails":email_collection}
    
    except Exception as e:
        logger.error(f"Error fetching carrier contacts: {e}")
        
        return {"status":"failed","message":"Internal Server Error","error":str(e)}

def get_header(token : str, content_type : str) -> dict:

    return {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type": content_type,
    }

async def send_email(email_data : dict, token: str, from_module : str, from_record_id : str):
    headers = get_header(token, "application/json")

    body = {
        "data": [
            {
            "from": {
                "user_name": "Centralfleet Dispatch Team",
                "email": "orders@centralfleet.ca"
            },
            "to": [
               email_data['to'],
            ],
            "subject": email_data['subject'],
            "content": email_data['html_content']

            }
        ]
        }
    
    if len(email_data['attachment_ids']):
    # The file attachment in the body
        body['data'][0]['attachments'] = [{"id": attachment_id} for attachment_id in email_data['attachment_ids']]

    logger.info(body)

    
    email_url = f"https://www.zohoapis.ca/crm/v2/{from_module}/{from_record_id}/actions/send_mail"
    
    response = requests.post(email_url,headers=headers,json=body)

    logger.info(response.json())

    return response

async def handle_send_dispatch_email(deal_id: str, quote_id: str, email_params : dict):
    token = TOKEN_INSTANCE.get_access_token()
    order_details = ZOHO_API.read_record(moduleName="Deals", id=deal_id, token=token).json().get("data", [{}])[0]
    try:
        attachments = ZOHO_API.fetch_related_list(moduleName="Deals",record_id=deal_id,token=token,name="Attachments").json().get("data", [])  
        email_params["attachment_ids"] = list()
        for attachment in attachments:
            file__name = attachment.get("File_Name")
            if file__name.startswith("RF-"):
                file_id = attachment.get("$file_id")
                email_params["attachment_ids"].append(file_id)
    except Exception as e:
        email_params["attachment_ids"] = list()
        logger.error(f"Error fetching attachments: {e}")
              
    quote_details = ZOHO_API.read_record(moduleName="Transport_Offers",id=quote_id,token=token).json().get("data", [])[0]    
    vehicle_details = ZOHO_API.fetch_related_list(moduleName="Deals",record_id=deal_id,token=token,name="Vehicles").json().get("data", [])
    
    vehicle_rows = EmailUtils.build_vehicle_rows(vehicle_details)    
    email_params["subject"] = f"New Transport Request: [{order_details.get('PickupLocation')} -> {order_details.get('Drop_off_Location')}]"
    assigned_carrier = FunctionalUtils.design_carrirer_body(quote_details)                                        # Assigned Carrier
    email_params["html_content"] = EmailUtils.get_dispatch_content(order_details, vehicle_rows, email_params.get("to").get("user_name"),
                                                                   assigned_carrier['Est_Pickup_Date_Range'],
                                                                   assigned_carrier['Delivery_Date_Range'],
                                                                   assigned_carrier['Carrier_Fee_Excl_tax'])
    email_response = await send_email(email_params,token, from_module="Deals", from_record_id=deal_id)
    if email_response.status_code== 200:
        slack_msg = f""" 
                        📧 Sucessfully Sent Dispatch Email to {email_params.get("to").get("user_name")}! \n *Details:* \n - Order ID: `{order_details.get("Deal_Name")}` \n - Type: `Dispatch` \n - Subject: `{email_params["subject"]}`"""
        FunctionalUtils.send_message_to_channel(os.getenv("BOT_TOKEN"), os.getenv("DISPATCH_CHANNEL_ID"),slack_msg)

        response = ZOHO_API.update_record(moduleName="Transport_Offers",id=quote_id,data={"data":[{"Approval_Status":"Accepted"}]},token=token)
        ZOHO_API.update_record(moduleName="Deals",id=deal_id,data={"data":[{"Stage":"Send Invoice",**assigned_carrier}]},token=token)
        return {"status":"success","message":"Successfully send Dispatch Email", "data":str(email_response),"redirect_url": f"https://crm.zohocloud.ca/crm/org110000402423/tab/Deals/{deal_id}"}
    else:
        logger.error(f"Error sending email: {email_response.text}")
        return {"status":"failed","message":"Failed to send Dispatch Email", "error":str(email_response)}
   

async def handle_send_quote_request(deal_id: str, email_params : dict, potentialid : str):
    token = TOKEN_INSTANCE.get_access_token()
    order_details = ZOHO_API.read_record(moduleName="Deals", id=deal_id, token=token).json().get("data", [{}])[0]
    vehicle_details = ZOHO_API.fetch_related_list(moduleName="Deals",record_id=deal_id,token=token,name="Vehicles").json().get("data", [])
    
    vehicle_rows = EmailUtils.build_vehicle_rows(vehicle_details)
    email_params["subject"] = f"Request for Transport Quote: [{order_details.get('PickupLocation')} -> {order_details.get('Drop_off_Location')}]"
    email_params["html_content"] = EmailUtils.get_QR_content(order_details, 
                                                         vehicle_rows, 
                                                         email_params.get("to").get("user_name"))

    email_params["attachment_ids"] = []
    email_response = await  send_email(email_params, token, from_module="Deals", from_record_id=deal_id)
    if email_response.status_code == 200:
        slack_msg = f"""
                    📧📜 {datetime.now()} *Email Sent Successfully!*  \n *Details:* \n - To: `{email_params.get("to").get("user_name")}` \n - Order ID: `{order_details.get('Deal_Name')}` \n - Email Type: `QuoteRequest` \n - Email Subject: '{email_params['subject']}` 
                """
        FunctionalUtils.send_message_to_channel(os.getenv("BOT_TOKEN"), os.getenv("QUOTE_CHANNEL_ID"),slack_msg)
        ZOHO_API.update_record(moduleName="Potential_Carrier", id=potentialid ,token=token,data={"data":[{"Progress_Status":"Connected"}]})
        return {"status":"success","message":"Successfully send Quote Request", "data":str(email_response.json()),"redirect_url": f"https://crm.zohocloud.ca/crm/org110000402423/tab/Deals/{deal_id}"}
    else:
        logger.error(f"Error sending email: {email_response.text}")
        return {"status":"failed","message":"Failed to send Quote Request Email", "error":str(email_response.json())}



async def handle_send_quote(deal_id: str, quote_id : str, email_params : dict, customerprice: str):
    token = TOKEN_INSTANCE.get_access_token()
    order_details = ZOHO_API.read_record(moduleName="Deals", id=deal_id, token=token).json().get("data", [{}])[0]
    vehicle_details = ZOHO_API.fetch_related_list(moduleName="Deals",record_id=deal_id,token=token,name="Vehicles").json().get("data", [])
    
    vehicle_rows = EmailUtils.build_vehicle_rows(vehicle_details)

    # EmailUtils.get_quote_html(order_details, vehicle_rows, email_params.get("to").get("user_name"))
    # email_response = await send_email(email_params, token, from_module="Deals", from_record_id=deal_id)

    ZOHO_API.update_record(moduleName="Transport_Offers",id=quote_id,token=token,data={"data":[{"Approval_Status":"Sent","Customer_Price_Excl_Tax":customerprice}]})
    ZOHO_API.update_record(moduleName="Deals",id=deal_id,token=token,data={"data":[{"Stage":"Await Customer Approval"}]})

    email_params["subject"] = f"Transport Quote: [{order_details.get('PickupLocation')} -> {order_details.get('Drop_off_Location')}]"

    return {"status":"success","message":"Successfully send Quote", "data":email_params,"redirect_url": f"https://crm.zohocloud.ca/crm/org110000402423/tab/Deals/{deal_id}"}




async def handle_send_invoice(deal_id: str, quote_id: str, email_params : dict, invoice_amount: str):
    token = TOKEN_INSTANCE.get_access_token()
    order_details = ZOHO_API.read_record(moduleName="Deals", id=deal_id, token=token).json().get("data", [{}])[0]
    attachments = ZOHO_API.fetch_related_list(moduleName="Deals",record_id=deal_id,token=token,name="Attachments").json().get("data", [])                     
    vehicle_details = ZOHO_API.fetch_related_list(moduleName="Deals",record_id=deal_id,token=token,name="Vehicles").json().get("data", [])
    
    file_id = None
    attachment_id = None
    file__name = None
    
    order_id = order_details.get("Deal_Name")

    for attachment in attachments:
        file__name = attachment.get("File_Name")
        if f"INVOICE-{order_id}" in file__name:
            file_id = attachment.get("$file_id")
            attachment_id = attachment.get("id")
            break
        
    email_params["attachment_ids"] = [file_id]

    if len(email_params["attachment_ids"])==1:
        
        file_name = file__name.replace("#", "%23")
        # Constructing the URL
        url = (
            f"https://crm.zohocloud.ca/crm/org110000402423/ViewAttachment?"
            f"fileId={file_id}&module=Potentials&parentId={deal_id}&creatorId=3384000000083001"
            f"&id={attachment_id}&name={file_name}&downLoadMode=pdfViewPlugin&attach=undefined"
        )

        email_params["subject"] = f"Invoice for Order {order_id}"
        email_params["html_content"] = EmailUtils.get_invoice_html(order_id, email_params.get("to").get("user_name"))

    email_response = await send_email(email_params,token, from_module="Deals", from_record_id=deal_id)

    if email_response.status_code == 200:
        ZOHO_API.update_record(moduleName="Deals",id=deal_id,token=token,data={"data":[{"Stage":"Confirm Delivery"}]})
        slack_msg = f"""
                    📧💸 Sucessfully Sent Invoice to {email_params.get("to").get("user_name")}!  \n *Details:* \n - Order ID: `{order_id}` \n - Invoiced Amount (Per Vehicle): `CAD {invoice_amount}` \n - Volumn : `{len(vehicle_details)} Vehicles` \n <{url}|View Invoice>
                    """
        FunctionalUtils.send_message_to_channel(os.getenv("BOT_TOKEN"), os.getenv("INVOICE_CHANNEL_ID"),slack_msg)
        return {"status":"success","message":"Successfully send Send Invoice Email", "data":str(email_response.json()),"redirect_url": f"https://crm.zohocloud.ca/crm/org110000402423/tab/Deals/{deal_id}"}
    
    else:
        logger.error(f"Error sending email: {email_response.text}")
        return {"status":"failed","message":"Failed to send Invoice Email", "error":str(email_response.json())}

async def handle_bulk_quote_request(carrier_id: str, email_params: dict, potentialid: str):
    """Handle bulk quote request for multiple potential deals."""

    try:
        potentialids = potentialid.split("|||")
        logger.info(f"Number of Deals to be Included in Bulk Request: {len(potentialids)}")
        
        token = TOKEN_INSTANCE.get_access_token()
        receiver_name = email_params.get("to").get("user_name")
        email_params["subject"] = "Request for Transport Quote"

        html_data = []

        # Fetch potential carrier details for all IDs concurrently
        tasks = [asyncio.to_thread(ZOHO_API.read_record, moduleName="Potential_Carrier", id=pid, token=token) for pid in potentialids]
        potential_carrier_responses = await asyncio.gather(*tasks)

        # Fetch order details and vehicles concurrently for each potential carrier
        order_name = []
        order_tasks = []
        vehicle_tasks = []
        for pc_response in potential_carrier_responses:
            pc_data = pc_response.json().get("data", [{}])[0]
            recommended_deal_id = pc_data.get("DealID", {}).get("id")
            logger.info(f"Recommended Deal ID: {recommended_deal_id}")

            # Add tasks for fetching order details and vehicles
            order_tasks.append(asyncio.to_thread(ZOHO_API.read_record, moduleName="Deals", id=recommended_deal_id, token=token))
            vehicle_tasks.append(asyncio.to_thread(ZOHO_API.fetch_related_list, moduleName="Deals", record_id=recommended_deal_id, token=token, name="Vehicles"))

        # Run all order and vehicle tasks concurrently
        order_responses = await asyncio.gather(*order_tasks)
        vehicle_responses = await asyncio.gather(*vehicle_tasks)

        # Process the responses
        for order_response, vehicle_response in zip(order_responses, vehicle_responses):
            order_data = order_response.json().get("data", [{}])[0]
            recommended_deal_name = order_data.get("Deal_Name")
            order_name.append(recommended_deal_name)
            pickup_location = order_data.get("PickupLocation")
            drop_off_location = order_data.get("Drop_off_Location")
            logger.info(f"Pickup Location: {pickup_location} and Drop Off Location: {drop_off_location}")

            vehicles_data = vehicle_response.json().get("data", [])

            # Append data for HTML content
            html_data.append({
                "OrderName": recommended_deal_name,
                "PickupLocation": pickup_location,
                "DropoffLocation": drop_off_location,
                "Vehicles": vehicles_data
            })

        # Generate HTML content and send email
        content = EmailUtils.get_bulk_quote_html(html_data, receiver_name)
        email_params["html_content"] = content
        email_params['attachment_ids'] = []

        email_response = await send_email(email_params, token, from_module="Vendors", from_record_id=carrier_id)
        logger.info(email_response.json())

        if email_response.status_code == 200:
            # Update progress status for all potential IDs
            update_data = {"data": [{"id": pid, "Progress_Status": "Connected"} for pid in potentialids]}
            update_response = await asyncio.to_thread(ZOHO_API.mass_update, moduleName="Potential_Carrier", data=update_data, token=token)
            logger.info(f"Update record response: {update_response.json()}")
            slack_msg = f"""
                        📧📜 {datetime.now()} *Email Sent Successfully!*  \n *Details:* \n - To: `{email_params.get("to").get("user_name")}` \n - Order ID: `{order_name}` \n - Email Type: `BulkQuoteRequest` \n - Email Subject: '{email_params['subject']}` 
                    """
            FunctionalUtils.send_message_to_channel(os.getenv("BOT_TOKEN"), os.getenv("QUOTE_CHANNEL_ID"),slack_msg)
            return {"status":"success","message":"Successfully send Bulk Quote Request Email", "data":str(email_response.json()),"redirect_url": f"https://crm.zohocloud.ca/crm/org110000402423/tab/Vendors/{carrier_id}"}
        
        else:
            logger.error(f"Error sending email: {email_response.text}")
            return {"status":"failed","message":"Failed to send Bulk Quote Request Email", "error":str(email_response.json())}



    except Exception as e:
        logger.error(f"An error occurred in handle_bulk_quote_request: {e}")

        return {"status":"failed","message":"Failed to send Bulk Quote Request Email", "error":str(e)}
    


async def handle_order_confirmation(deal_id: str, email_params : dict):

    token = TOKEN_INSTANCE.get_access_token()
    order_details = ZOHO_API.read_record(moduleName="Deals", id=deal_id, token=token).json().get("data", [{}])[0]
    email_params["attachment_ids"] = list()
    vehicle_details = ZOHO_API.fetch_related_list(moduleName="Deals",record_id=deal_id,token=token,name="Vehicles").json().get("data", [])
    
    vehicle_rows = EmailUtils.build_vehicle_rows(vehicle_details)    
    email_params["subject"] = f"Transport Order Received – [{order_details.get('Deal_Name')}]"

                               # Assigned Carrier
    email_params["html_content"] = EmailUtils.get_order_confirmation_html(order_details, vehicle_rows, email_params.get("to").get("user_name")
                                                                   )
    email_response = await send_email(email_params,token, from_module="Deals", from_record_id=deal_id)
    if email_response.status_code== 200:
        slack_msg = f""" 
                        📧 Sucessfully Sent Order Confirmation to {email_params.get("to").get("user_name")}! \n *Details:* \n - Order ID: `{order_details.get("Deal_Name")}` \n - Type: `OrderConfirmation` \n - Subject: `{email_params["subject"]}`"""
        FunctionalUtils.send_message_to_channel(os.getenv("BOT_TOKEN"), os.getenv("TRANSPORT_CHANNEL_ID"),slack_msg)
        return {"status":"success","message":"Successfully send Order Confirmation", "data":str(email_response),"redirect_url": f"https://crm.zohocloud.ca/crm/org110000402423/tab/Deals/{deal_id}"}
    else:
        logger.error(f"Error sending email: {email_response.text}")
        return {"status":"failed","message":"Failed to send Order Confirmation", "error":str(email_response)}
    

async def send_order_update(deal_ids: str, email_params : dict, customer_id : str):
    try:
        deal_ids_list = deal_ids.split("|||") ## orders
        logger.info(f"Number of Order to be sent as Update: {len(deal_ids_list)}")
        
        token = TOKEN_INSTANCE.get_access_token()
        receiver_name = email_params.get("to").get("user_name") 

        
        
        order_tasks = []
        vehicle_tasks = []
        for deal_id in deal_ids_list:
            order_tasks.append(asyncio.to_thread(ZOHO_API.read_record,moduleName="Deals",id=deal_id,token=token))
            vehicle_tasks.append(asyncio.to_thread(ZOHO_API.fetch_related_list, moduleName="Deals", record_id=deal_id, token=token, name="Vehicles"))

        # Run all order and vehicle tasks concurrently
        order_responses = await asyncio.gather(*order_tasks)
        vehicle_responses = await asyncio.gather(*vehicle_tasks)
        # Process the responses
       

        html_data = []
        for order_response, vehicle_response in zip(order_responses, vehicle_responses):
            logger.info(f"Order response type: {type(order_responses)}")
            logger.info(f"Vehicle response type: {type(vehicle_response)}")
            order_data = order_response.json().get("data", [{}])[0]
            logger.info(f"Order data: {order_data}")
            order_id = order_data.get("Deal_Name")
            createtime = order_data.get("Created_Time")
            order_status = order_data.get("Order_Status")
            pickup_location = order_data.get("PickupLocation")
            drop_off_location = order_data.get("Drop_off_Location")
            logger.info(f"Pickup Location: {pickup_location} and Drop Off Location: {drop_off_location}")

            vehicles_data = vehicle_response.json().get("data", [])
            if createtime:
                    createtime = datetime.fromisoformat(createtime[:19]).strftime("%Y-%m-%d")
                    
            # Append data for HTML content
            html_data.append({
                "CreateTime":createtime,
                "OrderName": order_id,
                "PickupLocation": pickup_location,
                "DropoffLocation": drop_off_location,
                "ETA": order_data.get("Delivery_Date_Range"),
                "Vehicles": vehicles_data
            })
        logger.info(html_data)
        order_row = EmailUtils.build_order_rows(html_data,for_request=True)
        email_params["html_content"] = EmailUtils.get_send_order_update_html(receiver_name, order_row)
        email_params['subject'] = "Update on Your Transport Orders"
        email_params['attachment_ids'] = []

        email_response = await send_email(email_params, token, from_module="Accounts", from_record_id=customer_id)


        if email_response.status_code == 200:
            slack_msg = f"""
                        📧📜 {datetime.now()} *Email Sent Successfully!*  \n *Details:* \n - To: `{email_params.get("to").get("user_name")}` \n - Email Type: `OrderUpdate` \n - Email Subject: '{email_params['subject']}` 
                    """
            FunctionalUtils.send_message_to_channel(os.getenv("BOT_TOKEN"), os.getenv("TRACKING_CHANNEL_ID"),slack_msg)
            return {"status":"success","message":"Successfully send Order Update Email", "data":str(email_response.json()),"redirect_url": f"https://crm.zohocloud.ca/crm/org110000402423/tab/Accounts/{customer_id}"}
        
        else:
            logger.error(f"Error sending email: {email_response.text}")
            return {"status":"failed","message":"Failed to send Order Update Email", "error":str(email_response.json())}


    except Exception as e:
        logger.error(f"An error occurred in send_order_update: {e}")

        return {"status":"failed","message":"Failed to send Order Update Email", "error":str(e)}



async def request_order_update(deal_ids: str, email_params : dict, carrier_id : str):
    try:
        deal_ids_list = deal_ids.split("|||") ## orderss
        logger.info(f" Carrier ID {carrier_id}")
        logger.info(f"Number of Order to be sent as Update: {len(deal_ids_list)}")
        
        token = TOKEN_INSTANCE.get_access_token()
        receiver_name = email_params.get("to").get("user_name") 

        
        
        order_tasks = []
        vehicle_tasks = []
        for deal_id in deal_ids_list:
            order_tasks.append(asyncio.to_thread(ZOHO_API.read_record,moduleName="Deals",id=deal_id,token=token))
            vehicle_tasks.append(asyncio.to_thread(ZOHO_API.fetch_related_list, moduleName="Deals", record_id=deal_id, token=token, name="Vehicles"))

        # Run all order and vehicle tasks concurrently
        order_responses = await asyncio.gather(*order_tasks)
        vehicle_responses = await asyncio.gather(*vehicle_tasks)
        # Process the responses
        

        html_data = []
        for order_response, vehicle_response in zip(order_responses, vehicle_responses):
            logger.info(f"Order response type: {type(order_responses)}")
            logger.info(f"Vehicle response type: {type(vehicle_response)}")
            order_data = order_response.json().get("data", [{}])[0]
            logger.info(f"Order data: {order_data}")
            order_id = order_data.get("Deal_Name")
            createtime = order_data.get("Created_Time")
            order_status = order_data.get("Order_Status")
            pickup_location = order_data.get("PickupLocation")
            drop_off_location = order_data.get("Drop_off_Location")
            logger.info(f"Pickup Location: {pickup_location} and Drop Off Location: {drop_off_location}")

            vehicles_data = vehicle_response.json().get("data", [])
            if createtime:
                    createtime = datetime.fromisoformat(createtime[:19]).strftime("%Y-%m-%d")
                    
            # Append data for HTML content
            html_data.append({
                "CreateTime":createtime,
                "OrderName": order_id,
                "PickupLocation": pickup_location,
                "DropoffLocation": drop_off_location,
                "Vehicles": vehicles_data
            })
        logger.info(html_data)
        order_row = EmailUtils.build_order_rows(html_data)
        email_params["html_content"] = EmailUtils.get_order_update_request_html(receiver_name, order_row)
        email_params['subject'] = "Request for ETA Updates on Transport Orders"
        email_params['attachment_ids'] = []
        

        email_response = await send_email(email_params, token, from_module="Vendors", from_record_id=carrier_id)


        if email_response.status_code == 200:
            slack_msg = f"""
                        📧📜 {datetime.now()} *Email Sent Successfully!*  \n *Details:* \n - To: `{email_params.get("to").get("user_name")}` \n - Email Type: `OrderRequest` \n - Email Subject: '{email_params['subject']}` 
                    """
            FunctionalUtils.send_message_to_channel(os.getenv("BOT_TOKEN"), os.getenv("TRACKING_CHANNEL_ID"), slack_msg)
            return {"status":"success","message":"Successfully send Order Update Email", "data":str(email_response.json()),"redirect_url": f"https://crm.zohocloud.ca/crm/org110000402423/tab/Vendors/{carrier_id}"}
        
        else:
            logger.error(f"Error sending email: {email_response.text}")
            return {"status":"failed","message":"Failed to send Order Update Email", "error":str(email_response.json())}

    except Exception as e:
        logger.error(f"An error occurred in send_order_update: {e}")

        return {"status":"failed","message":"Failed to send Order Update Email", "error":str(e)}



# async def is_quote_approved(deal_id : str, quote_id: str, user_selection: str):
#     if user_selection == "Confirm":
#         token = TOKEN_INSTANCE.get_access_token()
#         ZOHO_API.update_record(moduleName="Transport_Offers",id=quote_id,token=token,data={"data":[{"Approval_Status":"Accepted"}]})
#         ZOHO_API.update_record(moduleName="Deals",id=deal_id,token=token,data={"data":[{"Stage":"Dispatch Order"}]})
