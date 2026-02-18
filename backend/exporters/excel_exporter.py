"""
Excel Exporter

Export extraction results to Excel format with formatting.
"""

from pathlib import Path
from typing import Dict, Any
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from logger import logger
import config


class ExcelExporter:
    """Export structured data to Excel with formatting"""
    
    def __init__(self):
        """Initialize Excel exporter"""
        self.header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        self.header_font = Font(bold=True, color="FFFFFF")
        self.section_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        self.section_font = Font(bold=True)
        self.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
    
    def export(self, extraction_result: Dict[str, Any], output_path: str = None) -> str:
        """
        Export extraction result to Excel
        
        Args:
            extraction_result: Complete extraction result dictionary
            output_path: Optional custom output path
            
        Returns:
            Path to created Excel file
        """
        if not output_path:
            output_path = config.get_output_filename("extracted", ".xlsx")
        
        output_path = Path(output_path)
        
        wb = Workbook()
        wb.remove(wb.active)  # Remove default sheet
        
        # Create sheets
        self._create_summary_sheet(wb, extraction_result)
        
        if 'structured_data' in extraction_result:
            doc_type = extraction_result.get('classification', {}).get('document_type', 'unknown')
            
            if doc_type == 'invoice':
                self._create_invoice_sheet(wb, extraction_result)
            elif doc_type == 'resume':
                self._create_resume_sheet(wb, extraction_result)
            elif doc_type == 'contract':
                self._create_contract_sheet(wb, extraction_result)
        
        # Create confidence sheet if available
        if 'comprehensive_confidence' in extraction_result:
            self._create_confidence_sheet(wb, extraction_result)
        
        wb.save(output_path)
        logger.info(f"Exported to Excel: {output_path.name}")
        return str(output_path)
    
    def _create_summary_sheet(self, wb: Workbook, result: Dict[str, Any]):
        """Create summary sheet"""
        ws = wb.create_sheet("Summary")
        
        # Title
        ws['A1'] = "Extraction Summary"
        ws['A1'].font = Font(bold=True, size=14)
        ws.merge_cells('A1:B1')
        
        row = 3
        
        # Metadata
        metadata = result.get('metadata', {})
        ws[f'A{row}'] = "Document Information"
        ws[f'A{row}'].font = self.section_font
        ws[f'A{row}'].fill = self.section_fill
        row += 1
        
        for key, value in metadata.items():
            if not isinstance(value, (dict, list)):
                ws[f'A{row}'] = key.replace('_', ' ').title()
                ws[f'B{row}'] = str(value)
                row += 1
        
        row += 1
        
        # Classification
        if 'classification' in result:
            ws[f'A{row}'] = "AI Classification"
            ws[f'A{row}'].font = self.section_font
            ws[f'A{row}'].fill = self.section_fill
            row += 1
            
            classification = result['classification']
            ws[f'A{row}'] = "Document Type"
            ws[f'B{row}'] = classification.get('document_type', '')
            row += 1
            
            ws[f'A{row}'] = "Confidence"
            ws[f'B{row}'] = f"{classification.get('confidence', 0) * 100:.1f}%"
            row += 1
        
        # Auto-size columns
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 40
    
    def _create_invoice_sheet(self, wb: Workbook, result: Dict[str, Any]):
        """Create invoice data sheet"""
        ws = wb.create_sheet("Invoice Data")
        data = result['structured_data']
        
        row = 1
        
        # Header
        ws[f'A{row}'] = "Invoice Details"
        ws[f'A{row}'].font = self.section_font
        ws[f'A{row}'].fill = self.section_fill
        row += 1
        
        ws[f'A{row}'] = "Invoice Number"
        ws[f'B{row}'] = data.get('invoice_number', '')
        row += 1
        
        ws[f'A{row}'] = "Invoice Date"
        ws[f'B{row}'] = data.get('invoice_date', '')
        row += 1
        
        row += 1
        
        # Line items table
        ws[f'A{row}'] = "Line Items"
        ws[f'A{row}'].font = self.section_font
        ws[f'A{row}'].fill = self.section_fill
        row += 1
        
        # Table header
        headers = ['Description', 'Quantity', 'Unit Price', 'Total']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col)
            cell.value = header
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.alignment = Alignment(horizontal='center')
        row += 1
        
        # Line items
        for item in data.get('line_items', []):
            ws[f'A{row}'] = item.get('description', '')
            ws[f'B{row}'] = item.get('quantity', '')
            ws[f'C{row}'] = item.get('unit_price', '')
            ws[f'D{row}'] = item.get('total', '')
            row += 1
        
        row += 1
        ws[f'C{row}'] = "Subtotal"
        ws[f'C{row}'].font = Font(bold=True)
        ws[f'D{row}'] = data.get('subtotal', '')
        row += 1
        
        ws[f'C{row}'] = "Tax"
        ws[f'C{row}'].font = Font(bold=True)
        ws[f'D{row}'] = data.get('tax', '')
        row += 1
        
        ws[f'C{row}'] = "Total"
        ws[f'C{row}'].font = Font(bold=True, size=12)
        ws[f'D{row}'] = data.get('total', '')
        ws[f'D{row}'].font = Font(bold=True, size=12)
        
        # Auto-size columns
        ws.column_dimensions['A'].width = 40
        ws.column_dimensions['B'].width = 12
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 15
    
    def _create_resume_sheet(self, wb: Workbook, result: Dict[str, Any]):
        """Create resume data sheet"""
        ws = wb.create_sheet("Resume Data")
        data = result['structured_data']
        
        row = 1
        
        # Personal Info
        ws[f'A{row}'] = "Personal Information"
        ws[f'A{row}'].font = self.section_font
        ws[f'A{row}'].fill = self.section_fill
        row += 1
        
        personal = data.get('personal_info', {})
        ws[f'A{row}'] = "Name"
        ws[f'B{row}'] = personal.get('name', '')
        row += 1
        ws[f'A{row}'] = "Email"
        ws[f'B{row}'] = personal.get('email', '')
        row += 1
        
        row += 1
        
        # Experience table
        ws[f'A{row}'] = "Work Experience"
        ws[f'A{row}'].font = self.section_font
        ws[f'A{row}'].fill = self.section_fill
        row += 1
        
        headers = ['Company', 'Position', 'Location', 'Duration']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col)
            cell.value = header
            cell.font = self.header_font
            cell.fill = self.header_fill
        row += 1
        
        for exp in data.get('experience', []):
            ws[f'A{row}'] = exp.get('company', '')
            ws[f'B{row}'] = exp.get('position', '')
            ws[f'C{row}'] = exp.get('location', '')
            ws[f'D{row}'] = exp.get('duration', '')
            row += 1
        
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 30
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['D'].width = 20
    
    def _create_contract_sheet(self, wb: Workbook, result: Dict[str, Any]):
        """Create contract data sheet"""
        ws = wb.create_sheet("Contract Data")
        data = result['structured_data']
        
        row = 1
        ws[f'A{row}'] = "Contract Information"
        ws[f'A{row}'].font = self.section_font
        ws[f'A{row}'].fill = self.section_fill
        row += 1
        
        ws[f'A{row}'] = "Title"
        ws[f'B{row}'] = data.get('contract_title', '')
        row += 1
        
        ws[f'A{row}'] = "Type"
        ws[f'B{row}'] = data.get('contract_type', '')
        row += 1
        
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 50
    
    def _create_confidence_sheet(self, wb: Workbook, result: Dict[str, Any]):
        """Create confidence metrics sheet"""
        ws = wb.create_sheet("Confidence Metrics")
        conf = result['comprehensive_confidence']
        
        row = 1
        ws[f'A{row}'] = "Extraction Quality Metrics"
        ws[f'A{row}'].font = Font(bold=True, size=14)
        row += 2
        
        ws[f'A{row}'] = "Overall Confidence"
        ws[f'B{row}'] = f"{conf['overall_confidence'] * 100:.1f}%"
        ws[f'B{row}'].font = Font(bold=True, size=12)
        row += 1
        
        ws[f'A{row}'] = "Grade"
        ws[f'B{row}'] = conf['grade']
        ws[f'B{row}'].font = Font(bold=True, size=12)
        row += 2
        
        # Metrics
        ws[f'A{row}'] = "Detailed Metrics"
        ws[f'A{row}'].font = self.section_font
        ws[f'A{row}'].fill = self.section_fill
        row += 1
        
        for metric, value in conf['metrics'].items():
            ws[f'A{row}'] = metric.replace('_', ' ').title()
            ws[f'B{row}'] = f"{value * 100:.1f}%"
            row += 1
        
        row += 1
        
        # Explanations
        ws[f'A{row}'] = "Explanations"
        ws[f'A{row}'].font = self.section_font
        ws[f'A{row}'].fill = self.section_fill
        row += 1
        
        for explanation in conf.get('explanations', []):
            ws[f'A{row}'] = explanation
            row += 1
        
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 20
