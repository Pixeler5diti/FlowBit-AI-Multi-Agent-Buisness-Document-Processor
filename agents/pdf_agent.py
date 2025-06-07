import os
import json
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import google.generativeai as genai

class PDFAgent:
    """
    PDF Agent for extracting invoice totals and detecting regulatory keywords (GDPR, FDA).
    Uses Gemini 1.5 Flash for intelligent PDF content analysis.
    """
    
    def __init__(self):
        """Initialize the PDF agent"""
        self.logger = logging.getLogger(__name__)
        
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")
        genai.configure(api_key=api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Define detection patterns
        self.regulatory_keywords = ["GDPR", "FDA", "HIPAA", "SOX", "PCI", "ISO", "Compliance", "Regulation"]
        self.currency_patterns = ["$", "€", "£", "¥", "USD", "EUR", "GBP"]
        
        self.analysis_prompt = self._build_analysis_prompt()
        
    def _build_analysis_prompt(self) -> str:
        """Build the PDF analysis prompt for Gemini"""
        return f"""
You are an expert PDF document analyzer specializing in invoice processing and regulatory compliance detection. Analyze the provided PDF content:

1. INVOICE TOTAL EXTRACTION: Find monetary amounts, totals, subtotals, taxes
2. REGULATORY KEYWORD DETECTION: Search for compliance-related terms
3. DOCUMENT STRUCTURE: Identify document type and key sections

Target Keywords: {', '.join(self.regulatory_keywords)}
Currency Indicators: {', '.join(self.currency_patterns)}

Analysis Focus:
- Extract all monetary values (totals, subtotals, taxes, fees)
- Identify the main invoice total or final amount
- Detect regulatory compliance mentions
- Flag potential compliance requirements
- Analyze document structure and formatting

Respond ONLY with a valid JSON object in this exact format:
{{
    "invoice_total": "0.00",
    "currency": "USD",
    "monetary_values": [
        {{"label": "Subtotal", "amount": "100.00"}},
        {{"label": "Tax", "amount": "8.00"}},
        {{"label": "Total", "amount": "108.00"}}
    ],
    "regulatory_keywords_found": ["GDPR", "FDA"],
    "compliance_flags": [
        {{"keyword": "GDPR", "context": "data processing clause", "severity": "High"}},
        {{"keyword": "FDA", "context": "medical device approval", "severity": "Medium"}}
    ],
    "document_type": "Invoice",
    "key_sections": ["Header", "Line Items", "Total", "Terms"],
    "confidence_score": 0.95,
    "extraction_quality": "High",
    "reasoning": "Brief explanation of analysis"
}}

PDF Content to Analyze:
"""

    def analyze_pdf(self, content: str, filename: str = "unknown") -> Dict[str, Any]:
        """
        Analyze PDF content for invoice totals and regulatory keywords
        
        Args:
            content: The PDF content to analyze
            filename: The original filename (optional)
            
        Returns:
            Dictionary containing PDF analysis results
        """
        try:
            self.logger.info(f"Analyzing PDF: {filename}")
            
            # Prepare the full prompt
            full_prompt = self.analysis_prompt + f"\n\nFilename: {filename}\n\n{content[:4000]}"
            
            # Get analysis from Gemini
            response = self.model.generate_content(full_prompt)
            
            # Parse the response
            analysis_result = self._parse_gemini_response(response.text)
            
            # Add metadata
            analysis_result.update({
                "filename": filename,
                "timestamp": datetime.now().isoformat(),
                "content_length": len(content),
                "agent_type": "pdf",
                "model_used": "gemini-1.5-flash"
            })
            
            # Validate analysis
            validated_result = self._validate_analysis(analysis_result, content)
            
            self.logger.info(f"PDF analysis completed for {filename}: Found {len(validated_result['regulatory_keywords_found'])} regulatory keywords")
            
            return validated_result
            
        except Exception as e:
            self.logger.error(f"PDF analysis error for {filename}: {str(e)}")
            return self._create_fallback_analysis(content, filename, str(e))
    
    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Gemini's JSON response"""
        try:
            # Extract JSON from response if it contains other text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            raise ValueError(f"Invalid JSON response from Gemini: {e}")
    
    def _validate_analysis(self, result: Dict[str, Any], content: str) -> Dict[str, Any]:
        """Validate and normalize analysis results"""
        
        # Validate invoice total
        if not result.get("invoice_total") or result.get("invoice_total") == "0.00":
            result["invoice_total"] = self._extract_amounts_fallback(content)
        
        # Validate currency
        if not result.get("currency"):
            result["currency"] = self._detect_currency_fallback(content)
        
        # Validate monetary values
        if not result.get("monetary_values"):
            result["monetary_values"] = []
        
        # Validate regulatory keywords
        if not result.get("regulatory_keywords_found"):
            result["regulatory_keywords_found"] = self._detect_keywords_fallback(content)
        
        # Validate compliance flags
        if not result.get("compliance_flags"):
            result["compliance_flags"] = []
            for keyword in result["regulatory_keywords_found"]:
                result["compliance_flags"].append({
                    "keyword": keyword,
                    "context": "detected in document",
                    "severity": "Medium"
                })
        
        # Ensure confidence score is valid
        if not isinstance(result.get("confidence_score"), (int, float)) or not (0 <= result.get("confidence_score", 0) <= 1):
            result["confidence_score"] = 0.5
        
        # Ensure required fields exist
        if not result.get("document_type"):
            result["document_type"] = self._detect_document_type_fallback(content)
        
        if not result.get("key_sections"):
            result["key_sections"] = ["Content"]
        
        if not result.get("extraction_quality"):
            result["extraction_quality"] = "Medium"
        
        if not result.get("reasoning"):
            result["reasoning"] = "PDF analysis based on content extraction and pattern recognition"
        
        return result
    
    def _extract_amounts_fallback(self, content: str) -> str:
        """Fallback monetary amount extraction"""
        # Look for common total patterns
        total_patterns = [
            r'Total[:\s]*\$?([0-9,]+\.?[0-9]*)',
            r'Amount[:\s]*\$?([0-9,]+\.?[0-9]*)',
            r'Due[:\s]*\$?([0-9,]+\.?[0-9]*)',
            r'\$([0-9,]+\.?[0-9]*)',
            r'([0-9,]+\.[0-9]{2})'
        ]
        
        amounts = []
        for pattern in total_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            amounts.extend(matches)
        
        if amounts:
            # Return the largest amount found (likely the total)
            numeric_amounts = []
            for amount in amounts:
                try:
                    numeric_value = float(amount.replace(',', ''))
                    numeric_amounts.append(numeric_value)
                except ValueError:
                    continue
            
            if numeric_amounts:
                return f"{max(numeric_amounts):.2f}"
        
        return "0.00"
    
    def _detect_currency_fallback(self, content: str) -> str:
        """Fallback currency detection"""
        if '$' in content or 'USD' in content:
            return "USD"
        elif '€' in content or 'EUR' in content:
            return "EUR"
        elif '£' in content or 'GBP' in content:
            return "GBP"
        else:
            return "USD"  # Default
    
    def _detect_keywords_fallback(self, content: str) -> List[str]:
        """Fallback regulatory keyword detection"""
        found_keywords = []
        content_upper = content.upper()
        
        for keyword in self.regulatory_keywords:
            if keyword.upper() in content_upper:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _detect_document_type_fallback(self, content: str) -> str:
        """Fallback document type detection"""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ['invoice', 'bill', 'receipt']):
            return "Invoice"
        elif any(word in content_lower for word in ['contract', 'agreement']):
            return "Contract"
        elif any(word in content_lower for word in ['report', 'analysis']):
            return "Report"
        else:
            return "Document"
    
    def _create_fallback_analysis(self, content: str, filename: str, error: str) -> Dict[str, Any]:
        """Create a fallback analysis when Gemini fails"""
        
        return {
            "invoice_total": self._extract_amounts_fallback(content),
            "currency": self._detect_currency_fallback(content),
            "monetary_values": [],
            "regulatory_keywords_found": self._detect_keywords_fallback(content),
            "compliance_flags": [
                {
                    "keyword": kw,
                    "context": "detected in fallback analysis",
                    "severity": "Medium"
                } for kw in self._detect_keywords_fallback(content)
            ],
            "document_type": self._detect_document_type_fallback(content),
            "key_sections": ["Content"],
            "confidence_score": 0.3,
            "extraction_quality": "Low",
            "reasoning": f"Fallback analysis due to error: {error}",
            "filename": filename,
            "timestamp": datetime.now().isoformat(),
            "content_length": len(content),
            "agent_type": "pdf",
            "model_used": "fallback",
            "error": error
        }

    def simulate_api_response(self, analysis_result: Dict[str, Any]) -> None:
        """Simulate API response for compliance alerts"""
        regulatory_keywords = analysis_result.get("regulatory_keywords_found", [])
        if regulatory_keywords:
            print(f"POST /risk_alert - Regulatory keywords detected: {', '.join(regulatory_keywords)}")
            print(f"Response: {{'alert_id': 'pdf_{datetime.now().strftime('%Y%m%d_%H%M%S')}', 'status': 'created'}}")

    def run_pdf_agent(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main function to run PDF agent analysis - LangFlow compatible
        
        Args:
            input_data: Dictionary containing 'content' and optional 'filename'
            
        Returns:
            PDF analysis results
        """
        content = input_data.get('content', '')
        filename = input_data.get('filename', 'unknown')
        
        result = self.analyze_pdf(content, filename)
        
        # Simulate API call for regulatory compliance
        self.simulate_api_response(result)
        
        return result