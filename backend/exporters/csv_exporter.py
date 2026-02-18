"""
CSV Exporter

Export extraction results to CSV format.
"""

import csv
from pathlib import Path
from typing import Dict, Any, List
from logger import logger
import config


class CSVExporter:
    """Export structured data to CSV"""
    
    def export(self, extraction_result: Dict[str, Any], output_path: str = None) -> str:
        """
        Export extraction result to CSV
        
        Args:
            extraction_result: Complete extraction result dictionary
            output_path: Optional custom output path
            
        Returns:
            Path to created CSV file
        """
        if not output_path:
            output_path = config.get_output_filename("extracted", ".csv")
        
        output_path = Path(output_path)

        
        # Export based on document type
        if 'structured_data' in extraction_result:
            doc_type = extraction_result.get('classification', {}).get('document_type', 'unknown')
            
            if doc_type == 'invoice':
                return self._export_invoice(extraction_result, output_path)
            elif doc_type == 'resume':
                return self._export_resume(extraction_result, output_path)
            elif doc_type == 'contract':
                return self._export_contract(extraction_result, output_path)
            else:
                return self._export_generic(extraction_result, output_path)
        else:
            return self._export_generic(extraction_result, output_path)
    
    def _export_invoice(self, result: Dict[str, Any], output_path: Path) -> str:
        """Export invoice to CSV"""
        data = result['structured_data']
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header info
            writer.writerow(['Invoice Information'])
            writer.writerow(['Invoice Number', data.get('invoice_number', '')])
            writer.writerow(['Invoice Date', data.get('invoice_date', '')])
            writer.writerow(['Due Date', data.get('due_date', '')])
            writer.writerow([])
            
            # Vendor
            writer.writerow(['Vendor Information'])
            vendor = data.get('vendor', {})
            writer.writerow(['Name', vendor.get('name', '')])
            writer.writerow(['Address', vendor.get('address', '')])
            writer.writerow(['Email', vendor.get('email', '')])
            writer.writerow([])
            
            # Line items
            writer.writerow(['Line Items'])
            writer.writerow(['Description', 'Quantity', 'Unit Price', 'Total'])
            for item in data.get('line_items', []):
                writer.writerow([
                    item.get('description', ''),
                    item.get('quantity', ''),
                    item.get('unit_price', ''),
                    item.get('total', '')
                ])
            
            writer.writerow([])
            writer.writerow(['Subtotal', data.get('subtotal', '')])
            writer.writerow(['Tax', data.get('tax', '')])
            writer.writerow(['Total', data.get('total', '')])
        
        logger.info(f"Invoice exported to CSV: {output_path.name}")
        return str(output_path)
    
    def _export_resume(self, result: Dict[str, Any], output_path: Path) -> str:
        """Export resume to CSV"""
        data = result['structured_data']
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Personal info
            writer.writerow(['Personal Information'])
            personal = data.get('personal_info', {})
            writer.writerow(['Name', personal.get('name', '')])
            writer.writerow(['Email', personal.get('email', '')])
            writer.writerow(['Phone', personal.get('phone', '')])
            writer.writerow(['Location', personal.get('location', '')])
            writer.writerow([])
            
            # Experience
            writer.writerow(['Work Experience'])
            writer.writerow(['Company', 'Position', 'Location', 'Start Date', 'End Date', 'Duration'])
            for exp in data.get('experience', []):
                writer.writerow([
                    exp.get('company', ''),
                    exp.get('position', ''),
                    exp.get('location', ''),
                    exp.get('start_date', ''),
                    exp.get('end_date', ''),
                    exp.get('duration', '')
                ])
            
            writer.writerow([])
            
            # Education
            writer.writerow(['Education'])
            writer.writerow(['Institution', 'Degree', 'Field', 'Graduation', 'GPA'])
            for edu in data.get('education', []):
                writer.writerow([
                    edu.get('institution', ''),
                    edu.get('degree', ''),
                    edu.get('field_of_study', ''),
                    edu.get('graduation_date', ''),
                    edu.get('gpa', '')
                ])
        
        logger.info(f"Resume exported to CSV: {output_path.name}")
        return str(output_path)
    
    def _export_contract(self, result: Dict[str, Any], output_path: Path) -> str:
        """Export contract to CSV"""
        data = result['structured_data']
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            writer.writerow(['Contract Information'])
            writer.writerow(['Title', data.get('contract_title', '')])
            writer.writerow(['Type', data.get('contract_type', '')])
            writer.writerow(['Effective Date', data.get('effective_date', '')])
            writer.writerow(['Expiration Date', data.get('expiration_date', '')])
            writer.writerow([])
            
            writer.writerow(['Parties'])
            writer.writerow(['Name', 'Role', 'Address'])
            for party in data.get('parties', []):
                writer.writerow([
                    party.get('name', ''),
                    party.get('role', ''),
                    party.get('address', '')
                ])
        
        logger.info(f"Contract exported to CSV: {output_path.name}")
        return str(output_path)
    
    def _export_generic(self, result: Dict[str, Any], output_path: Path) -> str:
        """Export generic extraction result"""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            writer.writerow(['Metadata'])
            metadata = result.get('metadata', {})
            for key, value in metadata.items():
                if not isinstance(value, (dict, list)):
                    writer.writerow([key, value])
            
            writer.writerow([])
            writer.writerow(['Text'])
            writer.writerow(['Extracted Text'])
            text = result.get('text', {}).get('raw', '')
            writer.writerow([text[:500] + '...' if len(text) > 500 else text])
        
        logger.info(f"Generic extraction exported to CSV: {output_path.name}")
        return str(output_path)
