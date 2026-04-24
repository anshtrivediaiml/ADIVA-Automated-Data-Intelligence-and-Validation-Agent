"""
ADIVA - Invoice Schema

Schema definition for invoice documents, with full support for
Indian GST tax invoices (कर चालान / Tax Invoice).
"""

from typing import Dict, Any
from schemas.base_schema import BaseSchema


class InvoiceSchema(BaseSchema):
    """
    Schema for invoice documents — supports both international invoices
    and Indian GST tax invoices (CGST / SGST / IGST breakdown).
    """

    def get_schema(self) -> Dict[str, Any]:
        """Get invoice schema structure"""
        return {
            # ── Header ────────────────────────────────────────────────────────
            "invoice_number": "string",
            "invoice_date": "string (YYYY-MM-DD)",
            "due_date": "string (YYYY-MM-DD)",

            # ── Parties ───────────────────────────────────────────────────────
            "vendor": {
                "name": "string",
                "address": "string",
                "email": "string",
                "phone": "string",
                "gstin": "string (GST Identification Number, e.g. 27ABCDE1234F1Z5)"
            },
            "customer": {
                "name": "string",
                "address": "string",
                "email": "string",
                "phone": "string",
                "gstin": "string (customer GSTIN if present)"
            },

            # ── Line Items ────────────────────────────────────────────────────
            # COLUMN MAPPING (Hindi invoices):
            #   क्रम सं / Sr. No    → serial_number
            #   सामग्री का नाम      → item_name  (the product/service description)
            #   HSN/SAC कोड        → hsn_sac
            #   मात्रा / Qty        → quantity   ← this is a COUNT (e.g. 50 units)
            #   दर / Rate / Price   → unit_price ← price PER UNIT (e.g. ₹800)
            #   जीएसटी % / GST %   → gst_rate   ← percentage (e.g. 12)
            #   कुल राशि / Amount  → total      ← line total INCLUDING GST
            "line_items": [
                {
                    "serial_number": "number",
                    "item_name": "string (product or service name — the text label, NOT a number)",
                    "hsn_sac": "string (HSN or SAC code if present)",
                    "quantity": "number (count of units — typically a small integer like 50)",
                    "unit_price": "number (price per single unit — typically larger, e.g. 800)",
                    "gst_rate": "number (GST percentage for this line, e.g. 12 for 12%)",
                    "total": "number (line total = quantity × unit_price with GST included)"
                }
            ],

            # ── Totals ────────────────────────────────────────────────────────
            "subtotal": "number (sum of line totals before tax; उप-योग)",
            "cgst": "number (Central GST amount; सीजीएसटी)",
            "sgst": "number (State GST amount; एसजीएसटी)",
            "igst": "number (Integrated GST amount if inter-state; आईजीएसटी)",
            "tax": "number (total tax = cgst + sgst + igst)",
            "tax_rate": "number (overall effective tax rate % if single rate invoice)",
            "total": "number (grand total including all taxes; कुल योग)",

            # ── Additional Fields ──────────────────────────────────────────────
            "currency": "string (INR, USD, EUR, etc.)",
            "amount_in_words": "string (the written-out amount, e.g. 'One Lakh Sixty Two Thousand...')",
            "payment_terms": "string (e.g. 'Net 30', 'Due on receipt')",
            "bank_details": {
                "bank_name": "string",
                "branch": "string",
                "account_number": "string",
                "ifsc_code": "string"
            },
            "notes": "string (any other remarks not captured above)"
        }

    def get_prompt_instructions(self) -> str:
        """Get extraction instructions for invoices"""
        return """
You are extracting data from an INVOICE or TAX INVOICE (कर चालान) document.
The document may be in English, Hindi, or a mix of both.

═══════════════════════════════════════════════════════
CRITICAL: LINE ITEM COLUMN ORDER (read carefully!)
═══════════════════════════════════════════════════════
Indian invoices (कर चालान) typically have these columns in this order:
  Col 1: क्रम सं / Sr.No       → serial_number (1, 2, 3…)
  Col 2: सामग्री का नाम / Item → item_name     (TEXT label of the product)
  Col 3: मात्रा / Qty           → quantity      (small COUNT, e.g. 50, 30, 40)
  Col 4: दर / Rate / Price     → unit_price    (PRICE PER UNIT, e.g. 800, 1200)
  Col 5: जीएसटी % / GST%      → gst_rate      (tax %, e.g. 12, 5, 18)
  Col 6: कुल राशि / Amount     → total         (line total = qty × rate + GST)

DO NOT SWAP quantity and unit_price.
  ✓ Correct: quantity=50, unit_price=800, total=44800
  ✗ Wrong:   quantity=800, unit_price=50

IMPORTANT INSTRUCTIONS:
1. Extract ALL fields from the schema.
2. For missing information, use null.
3. For dates, use ISO format (YYYY-MM-DD).
4. For numbers, use numeric values only (no currency symbols, no commas).
5. For line_items: extract ALL rows from the item table.
6. item_name must be the TEXT description of the product/service, never a number.
7. Extract CGST and SGST separately (they are usually equal for intra-state transactions).
8. Extract amount_in_words exactly as printed (in English or transliterated Hindi).
9. Extract bank details including IFSC code if present.
10. Extract vendor GSTIN (जीएसटीआईएन) from the document header.
11. Default currency to INR for Indian invoices unless stated otherwise.

FIELD DETAILS:
- invoice_number  : Unique invoice/challan number (चालान संख्या)
- invoice_date    : Date the invoice was created (दिनांक)
- due_date        : Payment due date (देय तिथि)
- vendor          : Seller / विक्रेता विवरण
- customer        : Buyer / खरीदार विवरण
- line_items      : All rows in the item table (see column order above)
- subtotal        : Sum before tax (उप-योग)
- cgst            : Central GST charged (सीजीएसटी)
- sgst            : State GST charged (एसजीएसटी)
- igst            : IGST if inter-state (आईजीएसटी)
- tax             : Total tax = cgst + sgst (or igst)
- total           : Grand total including tax (कुल योग)
- amount_in_words : Written amount (शब्दों में राशि)
- bank_details    : Bank name, account number, IFSC code (IFSC कोड)

Extract precise information exactly as it appears. Do not guess or invent values.
"""

    def get_required_fields(self) -> list:
        """Get list of required fields"""
        return [
            'invoice_number',
            'invoice_date',
            'vendor.name',
            'total'
        ]
