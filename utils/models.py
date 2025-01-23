from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Quotes(BaseModel):
    Name : Optional[str] = None
    Carriers : Optional[str] = None
    Delivery_Date_Range : Optional[str] = None
    pickup_date_range : Optional[str] = None
    Dropoff_Location : Optional[str] = None
    Estimated_Amount : Optional[str] = None
    Pickup_Location	 : Optional[str] = None
    DealID: Optional[str] = None
    Approval_Status	 : Optional[str] = "Not Sent"
    VendorID : Optional[str] = None
    CreateDate: Optional[str] = None

    