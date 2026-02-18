"""
ADIVA - Resume Schema

Schema definition for resume/CV documents.
Defines the structure for extracting data from resumes.
"""

from typing import Dict, Any
from schemas.base_schema import BaseSchema


class ResumeSchema(BaseSchema):
    """
    Schema for resume/CV documents
    """
    
    def get_schema(self) -> Dict[str, Any]:
        """Get resume schema structure"""
        return {
            "personal_info": {
                "name": "string",
                "email": "string",
                "phone": "string",
                "location": "string (City, State/Country)",
                "linkedin": "string (URL)",
                "website": "string (URL)",
                "github": "string (URL)"
            },
            "professional_summary": "string (brief career summary)",
            "experience": [
                {
                    "company": "string",
                    "position": "string",
                    "location": "string",
                    "start_date": "string (YYYY-MM)",
                    "end_date": "string (YYYY-MM or 'Present')",
                    "duration": "string (calculated, e.g., '2 years 6 months')",
                    "responsibilities": ["string"],
                    "achievements": ["string"]
                }
            ],
            "education": [
                {
                    "institution": "string",
                    "degree": "string",
                    "field_of_study": "string",
                    "location": "string",
                    "graduation_date": "string (YYYY-MM)",
                    "gpa": "string",
                    "honors": "string"
                }
            ],
            "skills": {
                "technical": ["string"],
                "languages": ["string"],
                "tools": ["string"],
                "soft_skills": ["string"]
            },
            "certifications": [
                {
                    "name": "string",
                    "issuer": "string",
                    "date": "string (YYYY-MM)",
                    "credential_id": "string"
                }
            ],
            "projects": [
                {
                    "name": "string",
                    "description": "string",
                    "technologies": ["string"],
                    "url": "string"
                }
            ],
            "languages": [
                {
                    "language": "string",
                    "proficiency": "string (Native, Fluent, Professional, etc.)"
                }
            ]
        }
    
    def get_prompt_instructions(self) -> str:
        """Get extraction instructions for resumes"""
        return """
You are extracting data from a RESUME/CV document.

IMPORTANT INSTRUCTIONS:
1. Extract ALL relevant information found in the resume
2. For missing sections, use null or empty arrays
3. For dates, use YYYY-MM format
4. Calculate duration for work experience if not stated
5. Separate responsibilities from achievements
6. Group skills by category (technical, languages, tools, soft skills)
7. Extract ALL experiences chronologically (most recent first)
8. Extract ALL education entries
9. Include projects and certifications if present

FIELD DETAILS:
- personal_info: Contact details and online profiles
- professional_summary: The candidate's career summary/objective
- experience: Work history with responsibilities and achievements
- education: Academic background
- skills: Technical and soft skills, categorized
- certifications: Professional certifications
- projects: Notable projects (if mentioned)
- languages: Spoken languages and proficiency

Be thorough and extract all information present in the document.
"""
    
    def get_required_fields(self) -> list:
        """Get list of required fields"""
        return [
            'personal_info.name',
            'personal_info.email'
        ]
