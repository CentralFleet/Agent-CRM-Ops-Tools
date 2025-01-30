from pyzohocrm import ZohoApi,TokenManager
import os
from utils.helpers import EmailUtils, LoggingUtils, FunctionalUtils
from utils.models import *
import requests
import json

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
            Name = data.get("carrierName") + " - " + deal_details.get("Deal_Name"),
            CreateDate = datetime.now().strftime("%Y-%m-%d")  
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
                "CarrierName": data.get("carrierName"),
                "DropoffLocation":deal_details.get('Drop_off_Location'),
                "PickupLocation": deal_details.get('PickupLocation'),
                "EstimatedPickupTime": data.get('EstimatedPickupRange'),
                "EstimatedDropoffTime": data.get('DeliveryDate'),
                "Estimated_Amount": data.get('Estimated_Amount'),
                "Pickup_City":  deal_details.get("Pickup_City"),
                "Dropoff_City": deal_details.get("Dropoff_City"),
                "Tax_Province": deal_details.get("Tax_Province")
            }
            sqlquote_response = requests.post(url, json=new_sql_quote)
            return sqlquote_response.json()

    quote_crm_response = send_quote_to_crm()
    quote_id = quote_crm_response['data'][0]['details']['id']
    sql_response = send_quote_to_sql(quote_id=quote_id)
    ZOHO_API.update_record(moduleName="Deals",id=data.get('DealID'),token=token,data={"data":[{"Stage":"Send Quote to Customer","Order_Status":"Quote Ready"}]})
    ZOHO_API.update_record(moduleName="Potential_Carrier",id=data.get('PotentialID'),token=token,data={"data":[{"Progress_Status":"Quote Received"}]})
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
    logger.info(f"Triggered `get_contacts` for email type: {email_type} and {carrier_id}")
    try:
        token = TOKEN_INSTANCE.get_access_token()

        email_collection = {}
        if email_type == "Dispatch" or email_type == "QuoteRequest":   
                    carrier_contacts = ZOHO_API.fetch_related_list(moduleName="Vendors",record_id=carrier_id,token=token,name="Contact")
                    logger.info(carrier_contacts.json())
                    if carrier_contacts.status_code == 200:
                        for contact in carrier_contacts.json()['data']:
                            email_collection[contact['Email']] = contact['Last_Name']


        elif email_type == "SendQuote" or email_type == "SendInvoice":
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

def send_email(email_data : dict, token: str):
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

    
    email_url = f"https://www.zohoapis.ca/crm/v2/Deals/{email_data['zoho_deal_id']}/actions/send_mail"
    
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
            if f"INVOICE-{order_details.get('Deal_Name')}" not in file__name:
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
    email_response = send_email(email_params,token)
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
   

async def handle_send_quote_request(deal_id: str, quote_id : str, email_params : dict):
    token = TOKEN_INSTANCE.get_access_token()
    order_details = ZOHO_API.read_record(moduleName="Deals", id=deal_id, token=token).json().get("data", [{}])[0]
    vehicle_details = ZOHO_API.fetch_related_list(moduleName="Deals",record_id=deal_id,token=token,name="Vehicles").json().get("data", [])
    
    vehicle_rows = EmailUtils.build_vehicle_rows(vehicle_details)
    email_params["subject"] = f"Request for Transport Quote: [{order_details.get('PickupLocation')} -> {order_details.get('Drop_off_Location')}]"
    email_params["html_content"] = EmailUtils.get_QR_content(order_details, 
                                                         vehicle_rows, 
                                                         email_params.get("to").get("user_name"))

    email_params["attachment_ids"] = []
    email_response = send_email(email_params, token)
    if email_response.status_code == 200:
        slack_msg = f"""
                    📧📜 {datetime.now()} *Email Sent Successfully!*  \n *Details:* \n - To: `{email_params.get("to").get("user_name")}` \n - Order ID: `{order_details.get('Deal_Name')}` \n - Email Type: `QuoteRequest` \n - Email Subject: '{email_params['subject']}` 
                """
        FunctionalUtils.send_message_to_channel(os.getenv("BOT_TOKEN"), os.getenv("QUOTE_CHANNEL_ID"),slack_msg)
        return {"status":"success","message":"Successfully send Quote Request", "data":str(email_response.json()),"redirect_url": f"https://crm.zohocloud.ca/crm/org110000402423/tab/Deals/{deal_id}"}
    else:
        logger.error(f"Error sending email: {email_response.text}")
        return {"status":"failed","message":"Failed to send Quote Request Email", "error":str(email_response.json())}



async def handle_send_quote(deal_id: str, quote_id : str, email_params : dict, customerprice: str):
    token = TOKEN_INSTANCE.get_access_token()
    order_details = ZOHO_API.read_record(moduleName="Deals", id=deal_id, token=token).json().get("data", [{}])[0]
    vehicle_details = ZOHO_API.fetch_related_list(moduleName="Deals",record_id=deal_id,token=token,name="Vehicles").json().get("data", [])
    
    vehicle_rows = EmailUtils.build_vehicle_rows(vehicle_details)
    # email_response = send_email(email_params, token)

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

    email_response = send_email(email_params,token)

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
  

