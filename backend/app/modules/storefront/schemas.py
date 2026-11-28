"""Pydantic schemas for authenticated storefront catalog, artisans & retail orders."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ArtisanReviewItem(BaseModel):
    author: str
    city: str = "India"
    stars: int = 5
    text: str


class CatalogProductItem(BaseModel):
    listing_id: str
    product_id: str
    product_variant_id: str
    seller_profile_id: str
    seller_sku: str
    product_slug: str
    legacy_code: str | None = None
    title: str
    description: str | None = None
    category_slug: str
    category_name: str
    guild: str | None = None
    technique: str | None = None
    store_name: str
    artisan_name: str
    artisan_slug: str
    artisan_portrait_url: str | None = None
    workshop_district: str | None = None
    craft_specialty: str | None = None
    verification_path: str
    verification_status: str
    claimed_gi_code: str | None = None
    gi_level: int = 2
    purity_metric: str | None = None
    loom_hours: int | None = None
    dimensions: str | None = None
    rating: float = 4.9
    review_count: int = 0
    image_url: str | None = None
    gallery_images: list[str] = Field(default_factory=list)
    selling_price: Decimal
    compare_at_mrp: Decimal | None = None
    original_market_price: Decimal | None = None
    currency_code: str
    min_order_qty: int
    max_order_qty: int | None = None
    gi_status: str


class ArtisanSummaryItem(BaseModel):
    seller_profile_id: str
    slug: str
    name: str
    store_name: str
    craft_specialty: str | None = None
    workshop_district: str | None = None
    verification_path: str
    verification_status: str
    profile_status: str
    claimed_gi_code: str | None = None
    portrait_url: str | None = None
    bio: str | None = None
    credential: str | None = None
    since_year: int | None = None
    is_featured_showcase: bool = False
    featured_order: int = 999
    average_rating: Decimal = Decimal("4.90")
    total_reviews: int = 0
    reviews: list[ArtisanReviewItem] = Field(default_factory=list)
    listing_count: int = 0
    starting_price: Decimal | None = None
    categories: list[str] = Field(default_factory=list)


class ArtisanDetailResponse(ArtisanSummaryItem):
    listings: list[CatalogProductItem] = Field(default_factory=list)


class RetailOrderLineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seller_listing_id: str = Field(..., min_length=1, max_length=64)
    quantity: int = Field(..., ge=1, le=500)


class ShippingAddressInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=160)
    phone: str = Field(..., min_length=7, max_length=32)
    locality: str = Field(..., min_length=2, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(default="Jammu and Kashmir", min_length=2, max_length=100)
    pincode: str = Field(..., min_length=4, max_length=20)


class CreateRetailOrderRequest(BaseModel):
    """Browser sends ONLY listing IDs, quantities, shipping address, and payment method.

    Notice: No price, discount, or total field is accepted from the browser;
    FastAPI computes every monetary figure from MySQL seller_product_listings.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[RetailOrderLineInput] = Field(..., min_length=1, max_length=50)
    shipping_address: ShippingAddressInput
    payment_method: Literal["RAZORPAY_STANDARD", "COD"] = "RAZORPAY_STANDARD"
    payment_label: str | None = Field(default=None, max_length=120)


class SellerStudioListingInput(BaseModel):
    """Artisan Studio craft submission routed through all 10 ASIGS Guardrail layers."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=220)
    guild: str = Field(default="pashmina", min_length=2, max_length=64)
    technique: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    selling_price: Decimal = Field(..., gt=Decimal("0"))
    compare_at_mrp: Decimal | None = Field(default=None, gt=Decimal("0"))
    currency_code: str = Field(default="INR", min_length=3, max_length=3)
    stock_quantity: int = Field(default=1, ge=0)
    min_order_qty: int = Field(default=1, ge=1)
    seller_sku: str | None = Field(default=None, max_length=100)
    image_url: str | None = Field(default=None, max_length=512)
    loom_hours: int | None = Field(default=None, ge=1, le=50000)
    dimensions: str | None = Field(default=None, max_length=160)
    origin_district: str | None = Field(default=None, max_length=100)
    purity_metric: str | None = Field(default=None, max_length=255)
    requested_gi_status: str | None = Field(default=None, max_length=40)
    requested_listing_status: str | None = Field(default=None, max_length=40)


class RetailOrderItemSummary(BaseModel):
    product_id: str
    seller_listing_id: str
    title: str
    sku: str
    gi_status: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class RetailOrderSummaryResponse(BaseModel):
    order_id: str
    order_number: str
    order_scope: str = "RETAIL"
    payment_method: str
    payment_label: str | None = None
    payment_status: str
    fulfilment_status: str
    currency_code: str
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    shipping_fee: Decimal
    total_amount: Decimal
    item_count: int
    shipping_address: dict | None = None
    items: list[RetailOrderItemSummary] = Field(default_factory=list)
    created_at: datetime


class CreateProductReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(..., ge=1, le=5)
    title: str | None = Field(default=None, max_length=160)
    review_body: str = Field(..., min_length=5, max_length=2000)
    author_city: str | None = Field(default=None, max_length=100)


class ProductReviewItem(BaseModel):
    id: str
    product_id: str
    author_name: str
    author_city: str = "India"
    rating: int
    title: str | None = None
    review_body: str
    is_verified_purchase: bool = False
    seller_reply: str | None = None
    seller_replied_at: datetime | None = None
    created_at: datetime | None = None
    source: str = "database"


class RatingBreakdownItem(BaseModel):
    stars: int
    count: int
    percentage: int


class ProductReviewsSummaryResponse(BaseModel):
    product_id: str
    listing_id: str
    title: str
    average_rating: float
    total_reviews: int
    verified_purchase_count: int = 0
    rating_breakdown: list[RatingBreakdownItem] = Field(default_factory=list)
    reviews: list[ProductReviewItem] = Field(default_factory=list)
