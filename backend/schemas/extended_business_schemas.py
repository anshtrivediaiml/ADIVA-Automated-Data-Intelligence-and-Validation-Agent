"""
ADIVA - Extended Business Document Schemas

Additional schemas for business and finance documents that were previously
being forced into nearby but incorrect types.
"""

from typing import Dict, Any, List

from schemas.base_schema import BaseSchema


class PurchaseOrderSchema(BaseSchema):
    """Schema for purchase orders issued by a buyer to a vendor."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "purchase_order_number": "string",
            "order_date": "string (YYYY-MM-DD)",
            "delivery_date": "string (YYYY-MM-DD or null)",
            "buyer": {
                "name": "string",
                "address": "string",
                "email": "string",
                "phone": "string",
            },
            "vendor": {
                "name": "string",
                "address": "string",
                "email": "string",
                "phone": "string",
            },
            "line_items": [
                {
                    "description": "string",
                    "quantity": "number",
                    "unit_price": "number",
                    "total": "number",
                }
            ],
            "subtotal": "number",
            "tax": "number",
            "tax_rate": "number (percentage)",
            "total": "number",
            "currency": "string (default INR if not specified)",
            "payment_terms": "string",
            "notes": "string",
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a PURCHASE ORDER.

IMPORTANT INSTRUCTIONS:
1. purchase_order_number is the PO number, not an invoice number.
2. buyer is the issuing company; vendor is the supplier receiving the order.
3. delivery_date is often different from order_date.
4. Extract all ordered items with quantities, rates, and totals.
5. Keep payment terms exactly as written (for example, 'Net 30 Days').
6. Use null for missing fields.
7. Use numeric values for all monetary amounts.
8. Use YYYY-MM-DD for all dates.
"""

    def get_required_fields(self) -> List[str]:
        return [
            "purchase_order_number",
            "order_date",
            "buyer.name",
            "vendor.name",
            "total",
        ]


class RetailReceiptSchema(BaseSchema):
    """Schema for POS / retail receipts."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "receipt_number": "string",
            "receipt_date": "string (YYYY-MM-DD)",
            "receipt_time": "string (HH:MM:SS or null)",
            "merchant": {
                "name": "string",
                "address": "string",
                "phone": "string",
                "gstin": "string",
            },
            "customer_name": "string (or null for walk-in)",
            "cashier_name": "string",
            "line_items": [
                {
                    "description": "string",
                    "quantity": "number",
                    "unit_price": "number",
                    "total": "number",
                }
            ],
            "subtotal": "number",
            "tax": "number",
            "tax_rate": "number (percentage or null)",
            "total": "number",
            "payment_method": "string",
            "card_last4": "string (last 4 digits or masked form, if visible)",
            "currency": "string (default INR if not specified)",
            "notes": "string",
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a RETAIL RECEIPT or point-of-sale receipt.

IMPORTANT INSTRUCTIONS:
1. receipt_number is the receipt or bill number printed on the receipt.
2. merchant is the store issuing the receipt.
3. customer_name may be 'Walk-in' or null.
4. payment_method should be extracted exactly (cash, card, UPI, etc.).
5. If card details are masked, extract only the visible last 4 digits or masked text.
6. Sum taxes like CGST/SGST into tax when a single combined value is not printed.
7. Extract all item lines visible on the receipt.
8. Use numeric values for amounts and YYYY-MM-DD for dates.
"""

    def get_required_fields(self) -> List[str]:
        return [
            "receipt_number",
            "receipt_date",
            "merchant.name",
            "total",
        ]


class BillOfLadingSchema(BaseSchema):
    """Schema for ocean or airway bills of lading."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "bill_number": "string",
            "issue_date": "string (YYYY-MM-DD)",
            "shipper": {
                "name": "string",
                "address": "string",
            },
            "consignee": {
                "name": "string",
                "address": "string",
            },
            "notify_party": "string",
            "vessel_name": "string",
            "voyage_number": "string",
            "port_of_loading": "string",
            "port_of_discharge": "string",
            "final_destination": "string",
            "container_number": "string",
            "seal_number": "string",
            "package_count": "number",
            "goods_description": "string",
            "gross_weight": "number",
            "weight_unit": "string",
            "measurement": "string",
            "freight_terms": "string",
            "freight_amount": "number",
            "currency": "string",
            "shipment_date": "string (YYYY-MM-DD or null)",
            "carrier_signatory": "string",
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a BILL OF LADING.

IMPORTANT INSTRUCTIONS:
1. bill_number is the B/L number, not an invoice number.
2. shipper and consignee are the main parties to the shipment.
3. Extract vessel_name, voyage_number, loading port, discharge port, and final destination carefully.
4. package_count refers to the number of packages/cartons/containers listed.
5. gross_weight and measurement may be printed with units; separate the numeric value where possible.
6. freight_terms should preserve wording such as 'Freight Prepaid' or 'Freight Collect'.
7. freight_amount is the monetary freight charge if explicitly visible.
8. Use null for missing values and YYYY-MM-DD for dates.
"""

    def get_required_fields(self) -> List[str]:
        return [
            "bill_number",
            "issue_date",
            "shipper.name",
            "consignee.name",
            "goods_description",
        ]


class LabReportSchema(BaseSchema):
    """Schema for pathology and diagnostics lab reports."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "lab_name": "string",
            "lab_address": "string",
            "lab_phone": "string",
            "patient_name": "string",
            "patient_age": "string",
            "patient_gender": "string",
            "referred_by": "string",
            "sample_collected_date": "string (YYYY-MM-DD or null)",
            "report_name": "string",
            "report_date": "string (YYYY-MM-DD or null)",
            "test_results": [
                {
                    "test_name": "string",
                    "result": "string or number",
                    "units": "string",
                    "reference_range": "string",
                    "interpretation": "string",
                }
            ],
            "overall_impression": "string",
            "authorized_signatory": "string",
            "accreditation": "string",
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a LAB REPORT or pathology diagnostics report.

IMPORTANT INSTRUCTIONS:
1. This is NOT a prescription unless medicines are explicitly prescribed.
2. report_name is the investigation/test panel name (for example, CBC, LFT, Lipid Profile).
3. Extract all visible test rows into test_results.
4. Keep result values exactly as printed; they may be numeric or textual.
5. reference_range and interpretation should be preserved when present.
6. referred_by is the doctor or clinic that referred the patient.
7. authorized_signatory may be the lab director/pathologist signatory line.
8. Use null for missing values and YYYY-MM-DD for dates.
"""

    def get_required_fields(self) -> List[str]:
        return [
            "lab_name",
            "patient_name",
            "report_name",
            "test_results",
        ]


class PayslipSchema(BaseSchema):
    """Schema for salary slips / payslips."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "employer_name": "string",
            "payslip_month": "string (for example, 'February 2024')",
            "employee": {
                "name": "string",
                "employee_id": "string",
                "designation": "string",
                "department": "string",
                "pan": "string",
                "bank_account_masked": "string",
            },
            "pay_period": {
                "from_date": "string (YYYY-MM-DD)",
                "to_date": "string (YYYY-MM-DD)",
            },
            "earnings": [
                {
                    "component": "string",
                    "amount": "number",
                }
            ],
            "deductions": [
                {
                    "component": "string",
                    "amount": "number",
                }
            ],
            "total_earnings": "number",
            "total_deductions": "number",
            "net_pay": "number",
            "net_pay_words": "string",
            "currency": "string (default INR if not specified)",
            "issuer_name": "string",
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a PAYSLIP or SALARY SLIP.

IMPORTANT INSTRUCTIONS:
1. This is not Form 16 unless the document explicitly says Form 16/TDS certificate.
2. employer_name is the company issuing the payslip.
3. Extract all earnings components and all deductions components as lists.
4. net_pay_words should preserve the amount in words exactly as printed.
5. bank account values are often masked; extract the visible masked form.
6. pay_period.from_date and pay_period.to_date should be converted to YYYY-MM-DD.
7. Do not duplicate digits or concatenate amounts from adjacent OCR columns.
8. If printed totals are available, ensure sum(earnings)=total_earnings, sum(deductions)=total_deductions, and total_earnings-total_deductions=net_pay.
9. February 2024 may legitimately end on 2024-02-29 because 2024 is a leap year.
10. Use numeric values for amounts and null for missing values.
"""

    def get_required_fields(self) -> List[str]:
        return [
            "employer_name",
            "employee.name",
            "pay_period.from_date",
            "pay_period.to_date",
            "total_earnings",
            "total_deductions",
            "net_pay",
        ]


class BalanceSheetSchema(BaseSchema):
    """Schema for company balance sheets."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "entity_name": "string",
            "statement_date": "string (YYYY-MM-DD)",
            "currency": "string (default INR if not specified)",
            "assets": {
                "non_current_assets": [
                    {
                        "name": "string",
                        "amount": "number",
                    }
                ],
                "current_assets": [
                    {
                        "name": "string",
                        "amount": "number",
                    }
                ],
                "total_assets": "number",
            },
            "equity_and_liabilities": {
                "equity": [
                    {
                        "name": "string",
                        "amount": "number",
                    }
                ],
                "non_current_liabilities": [
                    {
                        "name": "string",
                        "amount": "number",
                    }
                ],
                "current_liabilities": [
                    {
                        "name": "string",
                        "amount": "number",
                    }
                ],
                "total_equity_and_liabilities": "number",
            },
            "prepared_by": "string",
            "notes": "string",
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from a BALANCE SHEET.

IMPORTANT INSTRUCTIONS:
1. statement_date is the date the balance sheet is stated as at.
2. Separate assets into non_current_assets and current_assets.
3. Separate equity and liabilities into equity, non_current_liabilities, and current_liabilities.
4. total_assets and total_equity_and_liabilities are critical totals.
5. Extract each visible line item with its amount.
6. If the same total appears on both sides, preserve it in both total fields.
7. Capital WIP is acceptable under non_current_assets if shown that way on the document.
8. Do not duplicate OCR rows across sections; each visible line item should appear once.
9. The sum of extracted section rows should match the printed totals when the document is clear.
10. Use numeric amounts without commas or currency symbols.
11. Use null for missing values.
"""

    def get_required_fields(self) -> List[str]:
        return [
            "entity_name",
            "statement_date",
            "assets.total_assets",
            "equity_and_liabilities.total_equity_and_liabilities",
        ]


class IncomeTaxAcknowledgmentSchema(BaseSchema):
    """Schema for ITR acknowledgment documents."""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "form_type": "string (for example, 'ITR-1 Acknowledgment')",
            "assessment_year": "string",
            "pan": "string",
            "taxpayer_name": "string",
            "address": "string",
            "acknowledgment_number": "string",
            "date_of_filing": "string (YYYY-MM-DD)",
            "filing_mode": "string",
            "verification_status": "string",
            "gross_total_income": "number",
            "total_tax_payable": "number",
            "tax_paid": "number",
            "refund_or_demand": "string",
            "refund_or_demand_amount": "number",
        }

    def get_prompt_instructions(self) -> str:
        return """
You are extracting data from an INCOME TAX ACKNOWLEDGMENT document such as an ITR acknowledgment.

IMPORTANT INSTRUCTIONS:
1. This is not Form 16 unless the document explicitly says Form 16/TDS certificate.
2. acknowledgment_number is the filed acknowledgment/reference number.
3. taxpayer_name is the filer name printed near the PAN and address.
4. refund_or_demand may be text like 'NIL', 'Refund', or 'Demand'.
5. tax_paid should capture the amount already paid/deposited.
6. Use numeric values for financial fields and YYYY-MM-DD for dates.
7. Use null for missing values.
"""

    def get_required_fields(self) -> List[str]:
        return [
            "assessment_year",
            "pan",
            "taxpayer_name",
            "acknowledgment_number",
            "date_of_filing",
        ]
