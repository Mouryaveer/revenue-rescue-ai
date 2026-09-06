"""
Payment endpoints for case-bound payment workflow.
"""

from app.api.v1.endpoints.razorpay_checkout import router as razorpay_router

# Export the razorpay checkout router as the payments router
# This provides the case-bound payment workflow endpoints
router = razorpay_router
