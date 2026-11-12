from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

class SubscriptionBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    merchant: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=50)
    price: float = Field(gt=0)
    currency: str = Field(default="USD", pattern="^(INR|USD)$")
    billing_interval: str = Field(default="monthly", pattern="^(monthly|yearly|weekly|custom)$")
    next_billing_date: date | None = None
    start_date: date | None = None
    status: str = Field(default="active", pattern="^(active|canceled)$")
    payment_method: str = "Card"
    website: str | None = None
    cancellation_url: str | None = None
    notes: str = ""
    usage_frequency: str = "unknown"

class SubscriptionCreate(SubscriptionBase): pass
class SubscriptionUpdate(SubscriptionBase): pass

class SubscriptionOut(SubscriptionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class PriceOut(BaseModel):
    id: int
    subscription_id: int
    old_price: float
    new_price: float
    currency: str
    change_date: datetime
    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

