"""
ADIVA - Invoice Schema

Schema definition for invoice documents.
Defines the structure for extracting data from invoices.
"""

from typing import Dict, Any
from schemas.base_schema import BaseSchema


class InvoiceSchema(BaseSchema):
    """
    Schema for invoice documents
    """
    
    def get_schema(self) -> Dict[str, Any]:
        """Get invoice schema structure"""
        return {
            "invoice_number": "string",
            "invoice_date": "string (YYYY-MM-DD)",
            "due_date": "string (YYYY-MM-DD)",
            "vendor": {
                "name": "string",
                "address": "string",
                "email": "string",
                "phone": "string"
            },
            "customer": {
                "name": "string",
                "address": "string",
                "email": "string",
                "phone": "string"
            },
            "line_items": [
                {
                    "description": "string",
                    "quantity": "number",
                    "unit_price": "number",
                    "total": "number"
                }
            ],
            "subtotal": "number",
            "tax": "number",
            "tax_rate": "number (percentage)",
            "total": "number",
            "currency": "string (USD, EUR, etc.)",
            "payment_terms": "string",
            "notes": "string"
        }
    
    def get_prompt_instructions(self) -> str:
        """Get extraction instructions for invoices"""
        return """
You are extracting data from an INVOICE document.

IMPORTANT INSTRUCTIONS:
1. Extract ALL fields from the schema
2. For missing information, use null
3. For dates, use ISO format (YYYY-MM-DD)
4. For numbers, use numeric values (not strings)
5. For line_items, extract ALL items found in the invoice
6. Calculate totals if not explicitly stated
7. Identify currency (default to USD if not specified)

FIELD DETAILS:
- invoice_number: The unique invoice identifier
- invoice_date: Date the invoice was created
- due_date: Payment due date
- vendor: The company/person issuing the invoice
- customer: The company/person receiving the invoice
- line_items: List of all items being charged
- subtotal: Sum of line items before tax
- tax: Tax amount
- total: Final amount to be paid
- payment_terms: Payment conditions (e.g., "Net 30", "Due on receipt")

Extract precise information as it appears in the document.
"""
    
    def get_required_fields(self) -> list:
        """Get list of required fields"""
        return [
            'invoice_number',
            'invoice_date',
            'vendor.name',
            'total'
        ]
