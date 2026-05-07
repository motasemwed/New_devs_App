from fastapi import APIRouter, Depends, HTTPException
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    
    tenant_id = getattr(current_user, "tenant_id", "default_tenant") or "default_tenant"
    
    revenue_data = await get_revenue_summary(property_id, tenant_id)
    
    # BUG FIX: Use Decimal instead of float() to avoid IEEE 754 precision errors
    # e.g. 333.333 + 333.333 + 333.334 = 999.9999999999999 with float
    total_revenue_decimal = Decimal(str(revenue_data['total'])).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    
    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": str(total_revenue_decimal),
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }