# Function to configure logging
import logging
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from collections import defaultdict
class LoggingUtils:
    def __init__(self):
        pass
    
    @classmethod
    def get_logger(cls,name):
        # Create a logger
        logger = logging.getLogger(name)
        
        # If the logger already has handlers, don't add more (this avoids duplicate logs)
        if not logger.hasHandlers():
            # Set logging level
            logger.setLevel(logging.INFO)
            
            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Create formatter and add it to the handler
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            
            # Add the console handler to the logger
            logger.addHandler(console_handler)
        
        return logger

class FunctionalUtils:
    def __init__(self):
        pass

    @classmethod
    def _get_date_range(cls,business_days_range,start_date=None):
        # Parse the range string (e.g., "1-2 business days")
        business_days = business_days_range.replace(" Business Days", "")
        min_days, max_days = map(int, business_days.split("-"))
        
        # Use today's date as the starting point
        if start_date is None:
            start_date = datetime.now()

        def add_business_days(date, days):
            """Helper function to add business days to a date."""
            current_date = date
            business_days_added = 0
            while business_days_added < days:
                current_date += timedelta(days=1)
                if current_date.weekday() < 5:  # Monday to Friday (0-4)
                    business_days_added += 1
            return current_date
        # Calculate the min and max dates
        min_date = add_business_days(start_date, min_days)
        max_date = add_business_days(start_date, max_days)

        if min_date == max_date:
            return f"{min_date.strftime('%Y-%m-%d')}"
        

        date_range = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
        
        return date_range
    
    @classmethod
    def design_carrirer_body(cls, quoteinfo):
        assigned_carrier = {}

        assigned_carrier['Vendor'] = quoteinfo.get("VendorID", {}).get("id")
        try:
            assigned_carrier["Est_Pickup_Date_Range"] = cls._get_date_range(quoteinfo.get('pickup_date_range'))
        except Exception as e:
            logging.error(f"Error calculating pickup date range: {e} -  {quoteinfo.get('pickup_date_range')}")
            assigned_carrier["Est_Pickup_Date_Range"] = ""

        try:
            # Delivery Date Calculate max Pickup date onwards
            assigned_carrier["Delivery_Date_Range"] = cls._get_date_range(quoteinfo.get('Delivery_Date_Range'))
        except Exception as e:
            logging.error(f"Error calculating delivery date range: {e} - {quoteinfo.get('Delivery_Date_Range')}")
            assigned_carrier["Delivery_Date_Range"] = ""

        assigned_carrier['dispatch_date'] = datetime.now().strftime('%Y-%m-%d')

        assigned_carrier['Carrier_Fee_Excl_tax'] = quoteinfo.get("Estimated_Amount")

        assigned_carrier['Customer_Price_Excl_Tax'] = quoteinfo.get("Customer_Price_Excl_Tax")

        return assigned_carrier

    @classmethod
    def send_message_to_channel(cls, bot_token, channel_id, message):
        client = WebClient(token=bot_token)

        try:
            response = client.chat_postMessage(
                channel=channel_id,
                text=message,
                unfurl_links=False,  # Disable link previews
        unfurl_media=False 
            )
            print(f"Message successfully sent to channel {channel_id} on Slack")
        except SlackApiError as e:
            print(f"Error sending Message to slack: {e}")
    
        # Helper function to read and replace placeholders in HTML files
    @classmethod
    def render_html_template(cls, filepath, placeholders):
        try:
            with open(filepath, 'r') as f:
                html_content = f.read()
            for placeholder, value in placeholders.items():
                html_content = html_content.replace(f"{{{{{placeholder}}}}}", value or "")
            return html_content
        except Exception as e:
            logging.error(f"Error reading or processing the HTML file: {e}")
            raise


class EmailUtils:

    def __init__(self):
        pass

    @classmethod
    def build_vehicle_rows(cls,vehicleinfo):
        rows = ""
        for vehicle in vehicleinfo:
            year = vehicle.get("Year", "")
            model = vehicle.get("Model", "")
            make = vehicle.get("Make", "")
            vin = vehicle.get("VIN", "")

            rows += f"""
            <tr>
                <td style="border: 1px solid black; padding: 8px;">{year}</td>
                <td style="border: 1px solid black; padding: 8px;">{make}</td>
                <td style="border: 1px solid black; padding: 8px;">{model}</td>
                <td style="border: 1px solid black; padding: 8px;">{vin}</td>
            </tr>
            """
        return rows

    @classmethod
    def get_dispatch_content(cls,orderinfo, vehicle_rows,receiver_name,pickup_date,delivery_date,carrierfee):
        pickup_location = orderinfo.get("PickupLocation")
        dropoff_location = orderinfo.get("Drop_off_Location")
        order_id = orderinfo.get("Deal_Name")
        customer_note = '' if orderinfo.get("special_instructon") == None else orderinfo.get("special_instructon") 
        
        try:
            carrierfee = "{:,}".format(int(carrierfee))
        except Exception as e:
            logging.error(f"Error Formatting Carrier Fee: {e}")

        content =  f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Hello <strong>{receiver_name}</strong>,</p>
                <p>We would like to proceed with the following transport. Please review the details below and let us know if you require any additional information.</p>

                <h3 style="color: #333;">Transport Summary</h3>
                <table style="border-collapse: collapse; width: 100%; table-layout: fixed; border: 1px solid black; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; width: 35%;">OrderID</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{order_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; color: black; width: 35%;">Pick-up Location</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{pickup_location}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; color: black; width: 35%;">Drop-off Location</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{dropoff_location}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; color: black; width: 35%;">Special Instructions</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{customer_note}</td>
                    </tr>
                </table>

                <h3 style="color: #333;">Vehicle Details</h3>
                <table style="border-collapse: collapse; width: 100%; border: 1px solid black; margin-bottom: 20px;">
                    <tr style="background-color: #f1f1f1; color: black;">
                        <th style="padding: 10px; text-align: left; border: 1px solid black;">Year</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid black;">Make</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid black;">Model</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid black;">VIN</th>
                    </tr>
                    {vehicle_rows}
                </table>

                <h3 style="color: #333;">ETA & Price</h3>
                <table style="border-collapse: collapse; width: 100%; table-layout: fixed; border: 1px solid black; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; color: black; width: 35%;">Est. Pick-up Date</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{pickup_date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; color: black; width: 35%;">Est. Delivery Date</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{delivery_date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; color: black; width: 35%;">Price Per Vehicle</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">${carrierfee}</td>
                    </tr>
                </table>

                <p>Thank you! Looking forward to your confirmation.</p>
                <p>Best regards,</p>
                <p><strong>Central Fleet Dispatch Team</strong></p>
                <p>Email: orders@centralfleet.ca</p>
                <p>Phone: 438-884-7462</p>
            </body>
        </html>
        """

        return content

    @classmethod
    def get_order_confirmation_html(cls,orderinfo, vehicle_rows, receiver_name: str):
        pickup_location = orderinfo.get("PickupLocation")
        dropoff_location = orderinfo.get("Drop_off_Location") 
        order_id = orderinfo.get("Deal_Name")
        customer_note = '' if orderinfo.get("special_instructon") == None else orderinfo.get("special_instructon") 
        return f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Hello <strong>{receiver_name}</strong>,</p>
                
                <p>We have received your transport request and will begin processing it shortly. Please find the details of your order below:</p>
                
                <h3 style="color: #333;">Transport Summary</h3>
                <table style="border-collapse: collapse; width: 100%; border: 1px solid black; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; width: 35%;">OrderID</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{order_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; width: 35%;">Pick-up Location</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{pickup_location}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; width: 35%;">Drop-off Location</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{dropoff_location}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; width: 35%;">Special Instructions</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{customer_note}</td>
                    </tr>
                </table>
                
                <h3 style="color: #333;">Vehicle Details</h3>
                <table style="border-collapse: collapse; width: 100%; border: 1px solid black; margin-bottom: 20px;">
                    <tr style="background-color: #f1f1f1;">
                        <th style="padding: 10px; border: 1px solid black;">Year</th>
                        <th style="padding: 10px; border: 1px solid black;">Make</th>
                        <th style="padding: 10px; border: 1px solid black;">Model</th>
                        <th style="padding: 10px; border: 1px solid black;">VIN</th>
                    </tr>
                    {vehicle_rows}
                </table>
                <p>We will keep you informed as your order progresses. If you have any questions or require any changes, please don't hesitate to contact us.</p>
                
                <p>Best regards,</p>
                <p><strong>Central Fleet Dispatch Team</strong></p>
                <p>Email: orders@centralfleet.ca</p>
                <p>Phone: 438-884-7462</p>
            </body>
            </html>
            """

    @classmethod
    def get_QR_content(cls, orderinfo, vehicle_rows, receiver_name):
        pickup_location = orderinfo.get("PickupLocation")
        dropoff_location = orderinfo.get("Drop_off_Location")

        content =  f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Dear <strong>{receiver_name}</strong>,</p>
                <p>We are currently exploring transport options and would appreciate it if you could share your best available rate for the shipment below, along with the earliest possible pick-up and delivery dates.</p>

                <h3 style="color: #333;">Transport Summary</h3>
                <table style="border-collapse: collapse; width: 100%; table-layout: fixed; border: 1px solid black; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; color: black; width: 35%;">Pick-up Location</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{pickup_location}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid black; font-weight: bold; background-color: #f1f1f1; color: black; width: 35%;">Drop-off Location</td>
                        <td style="padding: 8px; border: 1px solid black; width: 65%;">{dropoff_location}</td>
                    </tr>
                </table>

                <h3 style="color: #333;">Vehicle Details</h3>
                <table style="border-collapse: collapse; width: 100%; border: 1px solid black; margin-bottom: 20px;">
                    <tr style="background-color: #f1f1f1; color: black;">
                        <th style="padding: 10px; text-align: left; border: 1px solid black;">Year</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid black;">Make</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid black;">Model</th>
                        <th style="padding: 10px; text-align: left; border: 1px solid black;">VIN</th>
                    </tr>
                    {vehicle_rows}
                </table>
                <p>Thank you for your time. We look forward to your response!</p>
                <br>
                <p>Best regards,</p>
                <p><strong>Central Fleet Dispatch Team</strong></p>
                <p>Email: orders@centralfleet.ca</p>
                <p>Phone: 438-884-7462</p>
            </body>
        </html>
        """

        return content
    @classmethod
    def get_invoice_html(self,order_number, receiver_name):

        content=  f"""
             <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <p>Dear <strong>{receiver_name}</strong>,</p>
                <p>Thank you for choosing Central Fleet for your transport needs.</p>
                <p>Please find your invoice for Order <strong>{order_number}</strong> attached. If you have any questions or need assistance, feel free to contact us.<p>     
                <p>We appreciate your business and look forward to serving you again.</p>
                <br>
                <p>Best regards,</p>
                <p><strong>Central Fleet Dispatch Team</strong></p>
                <p>Email: orders@centralfleet.ca</p>
                <p>Phone: 438-884-7462</p>
            </body>
        </html>
        """

        return content
    
    @classmethod 
    def get_bulk_quote_html(cls, html_data, receiver_name):
        """
        Generates a plain HTML table with grouped pickup/dropoff locations, order names, and vehicles.

        Args:
            html_data (list): A list of dictionaries containing deal and vehicle information.
            receiver_name (str): The name of the recipient.

        Returns:
            str: The generated HTML as a string.
        """
        # Group vehicles by route (pickup + dropoff) and order name
        grouped_data = defaultdict(list)
        for deal in html_data:
            route_key = (deal["PickupLocation"], deal["DropoffLocation"], deal["OrderName"])
            grouped_data[route_key].extend(deal["Vehicles"])

        # Start building the HTML table
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Deal Summary</title>
        </head>
        <body>
            <p>Dear <strong>{receiver_name}</strong>,</p>
            <p>We currently have transportation orders and are seeking the most competitive quotes. Could you please provide your best price for the shipments listed below, along with the earliest possible pickup and delivery dates?</p>
            <table border="1" cellpadding="5" cellspacing="0" width="100%">
                <thead>
                    <tr>
                        <th>Order ID</th>
                        <th>Vehicles</th>
                        <th>Pickup Location</th>
                        <th>Dropoff Location</th>
                    </tr>
                </thead>
                <tbody>
        """

        # Add rows to the table
        for (pickup, dropoff, order_name), vehicles in grouped_data.items():
            # Calculate total vehicles for this route and order
            total_vehicles = len(vehicles)

            for i, vehicle in enumerate(vehicles):
                html_content += "<tr>"

                # Ensure Order ID is only shown once with rowspan
                if i == 0:
                    html_content += f'<td rowspan="{total_vehicles}">{order_name}</td>'

                html_content += f"""
                    <td>{vehicle.get('Year', '')} {vehicle.get('Make', '')} {vehicle.get('Model', '')} {vehicle.get('VIN','')}</td>
                """
                if i == 0:
                    html_content += f"""
                    <td rowspan="{total_vehicles}">{pickup}</td>
                    <td rowspan="{total_vehicles}">{dropoff}</td>
                    """
                html_content += """
                </tr>
                """

        # Close the HTML table
        html_content += """
                </tbody>
            </table>
            <p>Please provide your quote at the earliest. Thank you!</p>
            <p>Best Regards,</p>
            <p>Central Fleet Dispatch Team</p>
            <p>Email: orders@centralfleet.ca</p>
            <p>Phone: 438-884-7462</p>
        </body>
        </html>
        """

        return html_content
    
    # @classmethod
    # def get_quote_html(cls, orderinfo, vehicle_rows, receiver_name, pickup_date, delivery_date, customer_price, quote_id):
    #     """
    #     Generates an HTML email with transport order details, including action buttons for approval.

    #     Args:
    #         orderinfo (dict): Transport order details.
    #         vehicle_rows (str): HTML table rows for vehicle details.
    #         receiver_name (str): Customer's name.
    #         pickup_date (str): Estimated pickup date.
    #         delivery_date (str): Estimated delivery date.
    #         customer_price (str): Price per vehicle.
    #         quote_id (str): Unique quote ID for API calls.

    #     Returns:
    #         str: The generated HTML as a string.
    #     """

    #     pickup_location = orderinfo.get("PickupLocation")
    #     dropoff_location = orderinfo.get("Drop_off_Location")
    #     customer_note = orderinfo.get("special_instructon", "")

    #     accept_url = f"https://yourapi.com/quotes/{quote_id}/accept"
    #     decline_url = f"https://yourapi.com/quotes/{quote_id}/decline"

    #     content = f"""
    #     <html>
    #         <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    #             <p>Hello <strong>{receiver_name}</strong>,</p>
    #             <p>We have prepared a transport quote for your review. Please find the details below and let us know if you have any questions.</p>

    #             <h3 style="color: #333;">Transport Summary</h3>
    #             <table style="border-collapse: collapse; width: 100%; border: 1px solid black; margin-bottom: 20px;">
    #                 <tr>
    #                     <td style="padding: 10px; border: 1px solid black; background-color: #f1f1f1; font-weight: bold; width: 35%;">Pick-up Location</td>
    #                     <td style="padding: 10px; border: 1px solid black; width: 65%;">{pickup_location}</td>
    #                 </tr>
    #                 <tr>
    #                     <td style="padding: 10px; border: 1px solid black; background-color: #f1f1f1; font-weight: bold; width: 35%;">Drop-off Location</td>
    #                     <td style="padding: 10px; border: 1px solid black; width: 65%;">{dropoff_location}</td>
    #                 </tr>
    #                 <tr>
    #                     <td style="padding: 10px; border: 1px solid black; background-color: #f1f1f1; font-weight: bold; width: 35%;">Special Instructions</td>
    #                     <td style="padding: 10px; border: 1px solid black; width: 65%;">{customer_note}</td>
    #                 </tr>
    #             </table>

    #             <h3 style="color: #333;">Vehicle Details</h3>
    #             <table style="border-collapse: collapse; width: 100%; border: 1px solid black; margin-bottom: 20px;">
    #                 <tr style="background-color: #f1f1f1; font-weight: bold;">
    #                     <th style="padding: 10px; text-align: left; border: 1px solid black;">Year</th>
    #                     <th style="padding: 10px; text-align: left; border: 1px solid black;">Make</th>
    #                     <th style="padding: 10px; text-align: left; border: 1px solid black;">Model</th>
    #                     <th style="padding: 10px; text-align: left; border: 1px solid black;">VIN</th>
    #                 </tr>
    #                 {vehicle_rows}
    #             </table>

    #             <h3 style="color: #333;">ETA & Price</h3>
    #             <table style="border-collapse: collapse; width: 100%; border: 1px solid black; margin-bottom: 20px;">
    #                 <tr>
    #                     <td style="padding: 10px; border: 1px solid black; background-color: #f1f1f1; font-weight: bold; width: 35%;">Est. Pick-up Date</td>
    #                     <td style="padding: 10px; border: 1px solid black; width: 65%;">{pickup_date}</td>
    #                 </tr>
    #                 <tr>
    #                     <td style="padding: 10px; border: 1px solid black; background-color: #f1f1f1; font-weight: bold; width: 35%;">Est. Delivery Date</td>
    #                     <td style="padding: 10px; border: 1px solid black; width: 65%;">{delivery_date}</td>
    #                 </tr>
    #                 <tr>
    #                     <td style="padding: 10px; border: 1px solid black; background-color: #f1f1f1; font-weight: bold; width: 35%;">Price Per Vehicle</td>
    #                     <td style="padding: 10px; border: 1px solid black; width: 65%;">${customer_price}</td>
    #                 </tr>
    #             </table>

    #             <p>To proceed, please select one of the options below:</p>

    #             <div style="text-align: center; margin: 20px 0;">
    #                 <a href="{accept_url}" 
    #                    style="background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; font-size: 16px; border-radius: 5px; margin-right: 10px;">
    #                    Accept Quote
    #                 </a>
                    
    #                 <a href="{decline_url}" 
    #                    style="background-color: #dc3545; color: white; padding: 12px 24px; text-decoration: none; font-size: 16px; border-radius: 5px;">
    #                    Decline Quote
    #                 </a>
    #             </div>

    #             <p>If you have any questions, feel free to reach out.</p>

    #             <p>Best regards,</p>
    #             <p><strong>Central Fleet Dispatch Team</strong></p>
    #             <p>Email: <a href="mailto:orders@centralfleet.ca">orders@centralfleet.ca</a></p>
    #             <p>Phone: <a href="tel:4388847462">438-884-7462</a></p>
    #         </body>
    #     </html>
    #     """
    #     return content
