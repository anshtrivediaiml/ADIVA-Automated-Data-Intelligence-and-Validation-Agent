"""
ADIVA - Prescription Schema

Schema for medical prescriptions in English, Hindi, and Gujarati.
"""

from typing import Dict, Any, List
from schemas.base_schema import BaseSchema


class PrescriptionSchema(BaseSchema):
    """Schema for medical prescriptions / doctor notes"""

    def get_schema(self) -> Dict[str, Any]:
        return {
            "doctor_name": "string - Doctor's full name",
            "doctor_qualifications": "string - MBBS, MD, etc.",
            "clinic_name": "string - Name of clinic or hospital",
            "clinic_address": "string - Full address of clinic",
            "clinic_phone": "string - Contact number",
            "patient_name": "string - Patient's full name",
            "patient_age": "string - Patient's age",
            "patient_gender": "string - Male/Female/Other or null",
            "date": "string - Date of prescription (YYYY-MM-DD)",
            "medicines": [
                {
                    "name": "string - Medicine name (brand or generic)",
                    "dosage": "string - e.g. 500mg, 10ml",
                    "frequency": "string - e.g. twice daily, morning and night",
                    "duration": "string - e.g. 5 days, 1 week",
                    "instructions": "string - e.g. after meals, on empty stomach or null"
                }
            ],
            "diagnosis": "string - Diagnosis or chief complaint or null",
            "instructions": ["string - General health advice / instructions"],
            "follow_up": "string - Follow-up date or instructions or null",
            "registration_number": "string - Doctor's registration number or null"
        }

    def get_prompt_instructions(self) -> str:
        return """You are extracting structured data from a medical prescription.
The prescription may be in English, Hindi, or Gujarati.

Instructions:
- Extract ALL medicines listed with their complete dosage and duration
- Frequency examples: 'twice daily', 'morning-afternoon-night', 'सवारे-બपोरे-रात्रे'
- Duration examples: '5 days', '7 दिवस', '5 દિવસ'
- If a field is not present in the document, use null
- Preserve medicine names as written (may be brand names)
- Extract all health instructions/advice listed"""

    def get_required_fields(self) -> List[str]:
        return ['doctor_name', 'patient_name', 'date', 'medicines']
