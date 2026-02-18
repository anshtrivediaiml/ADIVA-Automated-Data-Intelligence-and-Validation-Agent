"""
ADIVA - Base Schema

Base class for all document schemas.
Defines the structure that all document type schemas must follow.
"""

from typing import Dict, Any, List
from abc import ABC, abstractmethod


class BaseSchema(ABC):
    """
    Abstract base class for document schemas
    """
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the schema definition
        
        Returns:
            Dictionary defining the schema structure
        """
        pass
    
    @abstractmethod
    def get_prompt_instructions(self) -> str:
        """
        Get instructions for LLM extraction
        
        Returns:
            String with extraction instructions
        """
        pass
    
    def get_required_fields(self) -> List[str]:
        """
        Get list of required field names
        
        Returns:
            List of required field paths (e.g., ['invoice_number', 'vendor.name'])
        """
        return []
    
    def validate_extracted_data(self, data: Dict[str, Any]) -> tuple:
        """
        Validate extracted data against schema
        
        Args:
            data: Extracted data dictionary
            
        Returns:
            Tuple of (is_valid, issues_list)
        """
        issues = []
        
        # Check for required fields
        for field in self.get_required_fields():
            if '.' in field:
                # Nested field
                parts = field.split('.')
                current = data
                for part in parts:
                    if not isinstance(current, dict) or part not in current:
                        issues.append(f"Missing required field: {field}")
                        break
                    current = current[part]
            else:
                # Top-level field
                if field not in data:
                    issues.append(f"Missing required field: {field}")
        
        is_valid = len(issues) == 0
        return is_valid, issues
