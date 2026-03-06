"""
Enhanced Confidence Scoring Module

Provides multi-metric confidence scoring for extraction quality.
"""

from datetime import date, datetime
from typing import Dict, Any, List, Optional
from schemas import get_schema


class ConfidenceScorer:
    """
    Calculate comprehensive confidence scores for extracted data
    """
    
    def __init__(self):
        """Initialize confidence scorer"""
        self.weights = {
            'schema_completeness': 0.35,  # Required fields present
            'data_quality': 0.25,         # Valid formats
            'field_confidence': 0.20,     # Individual field confidence
            'consistency': 0.15,          # Cross-field consistency
            'ocr_quality': 0.05          # OCR confidence (if applicable)
        }
    
    def calculate_comprehensive_confidence(
        self,
        extracted_data: Dict[str, Any],
        document_type: str,
        extraction_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive confidence metrics
        
        Args:
            extracted_data: Extracted structured data
            document_type: Type of document (invoice, resume, contract)
            extraction_metadata: Additional metadata (OCR scores, etc.)
            
        Returns:
            Dictionary with detailed confidence metrics
        """
        metrics = {}
        
        # 1. Schema Completeness
        metrics['schema_completeness'] = self._calculate_schema_completeness(
            extracted_data, document_type
        )
        
        # 2. Data Quality
        metrics['data_quality'] = self._calculate_data_quality(
            extracted_data, document_type
        )
        
        # 3. Field-Level Confidence
        metrics['field_confidence'] = self._calculate_field_confidence(
            extracted_data
        )
        
        # 4. Consistency Check
        metrics['consistency'] = self._calculate_consistency(
            extracted_data, document_type
        )
        
        # 5. OCR Quality (if applicable)
        if extraction_metadata and 'ocr_confidence' in extraction_metadata:
            metrics['ocr_quality'] = extraction_metadata['ocr_confidence']
        else:
            metrics['ocr_quality'] = 1.0  # No OCR used, perfect score
        
        # Calculate weighted overall score
        overall = sum(
            metrics[key] * self.weights[key] 
            for key in self.weights.keys()
        )
        
        # Add explanations
        explanations = self._generate_explanations(metrics)
        
        return {
            'overall_confidence': round(overall, 3),
            'metrics': {k: round(v, 3) for k, v in metrics.items()},
            'grade': self._get_confidence_grade(overall),
            'explanations': explanations,
            'recommendations': self._generate_recommendations(metrics)
        }
    
    def _calculate_schema_completeness(
        self, 
        data: Dict[str, Any], 
        doc_type: str
    ) -> float:
        """Calculate what percentage of required fields are present"""
        schema = get_schema(doc_type)
        if not schema:
            return 1.0
        
        required_fields = schema.get_required_fields()
        if not required_fields:
            return 1.0
        
        present_count = 0
        for field in required_fields:
            if self._is_field_present(data, field):
                present_count += 1
        
        return present_count / len(required_fields)
    
    def _calculate_data_quality(
        self, 
        data: Dict[str, Any], 
        doc_type: str
    ) -> float:
        """Calculate quality based on valid formats and non-null values"""
        if not data:
            return 0.0
        
        total_fields = 0
        valid_fields = 0
        
        def check_field(value, parent_key=''):
            nonlocal total_fields, valid_fields
            
            if isinstance(value, dict):
                for k, v in value.items():
                    check_field(v, f"{parent_key}.{k}" if parent_key else k)
            elif isinstance(value, list):
                total_fields += 1
                if value:  # Non-empty list
                    valid_fields += 1
            else:
                total_fields += 1
                if value is not None and str(value).strip():
                    valid_fields += 1
        
        check_field(data)
        
        return valid_fields / total_fields if total_fields > 0 else 0.0
    
    def _calculate_field_confidence(self, data: Dict[str, Any]) -> float:
        """
        Calculate average confidence if fields have individual confidence scores
        For now, returns 1.0 (placeholder for future LLM field-level confidence)
        """
        # TODO: Extract field-level confidence from LLM responses
        # For now, assume high confidence
        return 0.9

    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse common date representations into a date, else None."""
        if value is None:
            return None

        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        text = str(value).strip()
        if not text:
            return None

        if text.lower() in {"present", "current", "ongoing", "till date"}:
            return None

        normalized = text.replace("/", "-").replace(".", "-")
        formats = (
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%d-%m-%y",
            "%m-%d-%y",
            "%b %Y",
            "%B %Y",
            "%Y-%m",
            "%Y",
        )
        for fmt in formats:
            try:
                parsed = datetime.strptime(normalized, fmt)
                return parsed.date().replace(day=1) if fmt in {"%b %Y", "%B %Y", "%Y-%m", "%Y"} else parsed.date()
            except ValueError:
                continue

        return None
    
    def _calculate_consistency(
        self, 
        data: Dict[str, Any], 
        doc_type: str
    ) -> float:
        """Check for logical consistency in data"""
        score = 1.0
        issues = 0
        checks = 0
        
        if doc_type == 'invoice':
            # Check if totals are consistent
            if 'line_items' in data and 'subtotal' in data:
                checks += 1
                calculated_subtotal = sum(
                    (item.get('total') or 0)   # coerce None → 0
                    for item in data.get('line_items', [])
                )
                stated_subtotal = data.get('subtotal') or 0   # coerce None → 0
                if stated_subtotal > 0 and abs(calculated_subtotal - stated_subtotal) > 0.01:
                    issues += 1
        
        elif doc_type == 'resume':
            # Check date consistency
            if 'experience' in data:
                for exp in data.get('experience', []):
                    checks += 1
                    start = self._parse_date(exp.get('start_date'))
                    end = self._parse_date(exp.get('end_date'))
                    if start and end and start > end:
                        issues += 1
        
        elif doc_type == 'contract':
            # Check date logic
            if 'effective_date' in data and 'expiration_date' in data:
                checks += 1
                effective_date = self._parse_date(data.get('effective_date'))
                expiration_date = self._parse_date(data.get('expiration_date'))
                if effective_date and expiration_date and effective_date > expiration_date:
                    issues += 1
        
        if checks == 0:
            return 1.0
        
        return 1.0 - (issues / checks)
    
    def _is_field_present(self, data: Dict[str, Any], field_path: str) -> bool:
        """Check if a field path exists and has a non-null value"""
        parts = field_path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        
        return current is not None and (
            not isinstance(current, str) or current.strip()
        )
    
    def _get_confidence_grade(self, score: float) -> str:
        """Convert confidence score to letter grade"""
        if score >= 0.95:
            return 'A+'
        elif score >= 0.90:
            return 'A'
        elif score >= 0.85:
            return 'B+'
        elif score >= 0.80:
            return 'B'
        elif score >= 0.75:
            return 'C+'
        elif score >= 0.70:
            return 'C'
        else:
            return 'D'
    
    def _generate_explanations(self, metrics: Dict[str, float]) -> List[str]:
        """Generate human-readable explanations for scores"""
        explanations = []
        
        if metrics['schema_completeness'] < 1.0:
            missing_pct = (1 - metrics['schema_completeness']) * 100
            explanations.append(
                f"⚠️ {missing_pct:.0f}% of required fields are missing"
            )
        else:
            explanations.append("✅ All required fields are present")
        
        if metrics['data_quality'] < 0.8:
            explanations.append("⚠️ Some fields have missing or invalid data")
        else:
            explanations.append("✅ Data quality is good")
        
        if metrics['consistency'] < 1.0:
            explanations.append("⚠️ Some inconsistencies detected in data")
        
        if metrics['ocr_quality'] < 0.9:
            explanations.append("⚠️ OCR confidence is below optimal (scanned document)")
        
        return explanations
    
    def _generate_recommendations(self, metrics: Dict[str, float]) -> List[str]:
        """Generate recommendations for improving confidence"""
        recommendations = []
        
        if metrics['schema_completeness'] < 0.9:
            recommendations.append(
                "Review document to fill in missing required fields"
            )
        
        if metrics['data_quality'] < 0.8:
            recommendations.append(
                "Manually verify and correct invalid or missing field values"
            )
        
        if metrics['consistency'] < 0.9:
            recommendations.append(
                "Check for logical errors (e.g., totals, dates)"
            )
        
        if metrics['ocr_quality'] < 0.8:
            recommendations.append(
                "Consider rescanning document at higher DPI (300+ recommended)"
            )
        
        if not recommendations:
            recommendations.append("✅ Extraction quality is excellent!")
        
        return recommendations
