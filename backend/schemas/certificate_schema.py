"""
ADIVA - Certificate Schema

Schema for official certificates: marriage, birth, death, educational.
Supports English, Hindi, and Gujarati.
"""

from typing import Dict, Any, List
from schemas.base_schema import BaseSchema


class CertificateSchema(BaseSchema):
    """Schema for official certificates"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "certificate_type": "string - e.g. Marriage Certificate, Birth Certificate, Educational Certificate",
            "certificate_number": "string - Registration/certificate number",
            "issuing_authority": "string - Name of issuing organization (e.g. Municipal Corporation, University)",
            "issuing_authority_address": "string - Address of issuing authority or null",
            "issue_date": "string - Date of issue (YYYY-MM-DD)",
            "primary_person": {
                "name": "string - Main person's name (bride/groom/student/child)",
                "age": "string - Age or null",
                "address": "string - Address or null",
                "father_name": "string - Father's name or null",
                "religion": "string - Religion or null"
            },
            "secondary_person": {
                "name": "string - Second person's name (for marriage: other party) or null",
                "age": "string - Age or null",
                "address": "string - Address or null",
                "father_name": "string - Father's name or null",
                "religion": "string - Religion or null"
            },
            "event_date": "string - Date of the event (marriage/birth/graduation) (YYYY-MM-DD) or null",
            "event_place": "string - Place where event occurred or null",
            "witnesses": ["string - Witness names"],
            "registrar_name": "string - Name of registrar/signing authority or null",
            "additional_details": "object - Any other relevant key-value pairs from the certificate"
        }

    def get_prompt_instructions(self) -> str:
        return """You are extracting structured data from an official certificate document.
The certificate may be in English, Hindi, or Gujarati.

Instructions:
- Identify the certificate type from context (marriage, birth, educational, etc.)
- For marriage certificates: primary_person = groom, secondary_person = bride (or vice versa)
- For birth/educational certificates: primary_person = the main subject, secondary_person = null
- Extract the registration/certificate number carefully — it's usually prominent
- event_date = when the event happened; issue_date = when the certificate was issued
- Extract all witness names as a list
- Use additional_details for any other structured information not covered above"""

    def get_required_fields(self) -> List[str]:
        return ['certificate_type', 'certificate_number', 'issuing_authority', 'issue_date', 'primary_person.name']
