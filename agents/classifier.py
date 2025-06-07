import os
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
import google.generativeai as genai

class ClassifierAgent:
    """
    Classifier Agent for document format and business intent classification.
    Uses Gemini 1.5 Flash for intelligent classification.
    """
    
    def __init__(self):
        """Initialize the classifier agent"""
        self.logger = logging.getLogger(__name__)
        
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")
        genai.configure(api_key=api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Define classification schemas
        self.format_types = ["Email", "JSON", "PDF"]
        self.business_intents = ["RFQ", "Complaint", "Invoice", "Regulation", "Fraud Risk"]
        
        # Define classification prompts
        self.classification_prompt = self._build_classification_prompt()
        
    def _build_classification_prompt(self) -> str:
        """Build the classification prompt for Gemini"""
        return f"""
You are an expert document classifier. Analyze the provided document content and classify it according to two dimensions:

1. DOCUMENT FORMAT: Classify as one of: {', '.join(self.format_types)}
2. BUSINESS INTENT: Classify as one of: {', '.join(self.business_intents)}

Classification Guidelines:

FORMAT CLASSIFICATION:
- Email: Contains email headers (From, To, Subject), email addresses, typical email structure
- JSON: Valid or invalid JSON structure, key-value pairs, nested objects/arrays
- PDF: PDF content markers, invoice layouts, formatted documents, or mentions PDF structure

BUSINESS INTENT CLASSIFICATION:
- RFQ (Request for Quote): Requests for pricing, quotes, proposals, procurement inquiries
- Complaint: Customer complaints, dissatisfaction, service issues, product problems
- Invoice: Bills, payment requests, financial transactions, accounting documents
- Regulation: Legal compliance, policy documents, regulatory requirements, GDPR, FDA mentions
- Fraud Risk: Suspicious activities, security concerns, anomalous patterns, risk indicators

Respond ONLY with a valid JSON object in this exact format:
{{
    "document_format": "one of the format types",
    "business_intent": "one of the business intents",
    "confidence_score": 0.95,
    "reasoning": "Brief explanation of classification decision",
    "key_indicators": ["indicator1", "indicator2", "indicator3"]
}}

Document Content to Classify:
"""

    def classify_document(self, content: str, filename: str = "unknown") -> Dict[str, Any]:
        """
        Classify a document's format and business intent
        
        Args:
            content: The document content to classify
            filename: The original filename (optional)
            
        Returns:
            Dictionary containing classification results
        """
        try:
            self.logger.info(f"Classifying document: {filename}")
            
            # Prepare the full prompt
            full_prompt = self.classification_prompt + f"\n\nFilename: {filename}\n\n{content[:2000]}"
            
            # Get classification from Gemini
            response = self.model.generate_content(full_prompt)
            
            # Parse the response
            classification_result = self._parse_gemini_response(response.text)
            
            # Add metadata
            classification_result.update({
                "filename": filename,
                "timestamp": datetime.now().isoformat(),
                "content_length": len(content),
                "agent_type": "classifier",
                "model_used": "gemini-1.5-flash"
            })
            
            # Validate classification
            validated_result = self._validate_classification(classification_result)
            
            self.logger.info(f"Classification completed for {filename}: {validated_result['document_format']} / {validated_result['business_intent']}")
            
            return validated_result
            
        except Exception as e:
            self.logger.error(f"Classification error for {filename}: {str(e)}")
            return self._create_fallback_classification(content, filename, str(e))
    
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
    
    def _validate_classification(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize classification results"""
        
        # Validate document format
        if result.get("document_format") not in self.format_types:
            self.logger.warning(f"Invalid format type: {result.get('document_format')}")
            result["document_format"] = self._fallback_format_classification(result.get("filename", ""))
        
        # Validate business intent
        if result.get("business_intent") not in self.business_intents:
            self.logger.warning(f"Invalid business intent: {result.get('business_intent')}")
            result["business_intent"] = "RFQ"  # Default fallback
        
        # Ensure confidence score is valid
        if not isinstance(result.get("confidence_score"), (int, float)) or not (0 <= result.get("confidence_score", 0) <= 1):
            result["confidence_score"] = 0.5
        
        # Ensure required fields exist
        if not result.get("reasoning"):
            result["reasoning"] = "Classification based on content analysis"
        
        if not result.get("key_indicators"):
            result["key_indicators"] = ["content_analysis"]
        
        return result
    
    def _fallback_format_classification(self, filename: str) -> str:
        """Fallback format classification based on filename"""
        filename_lower = filename.lower()
        
        if filename_lower.endswith(('.pdf',)):
            return "PDF"
        elif filename_lower.endswith(('.json',)):
            return "JSON"
        elif filename_lower.endswith(('.eml', '.msg', '.txt')):
            return "Email"
        else:
            return "Email"  # Default fallback
    
    def _create_fallback_classification(self, content: str, filename: str, error: str) -> Dict[str, Any]:
        """Create a fallback classification when Gemini fails"""
        
        # Simple rule-based fallback
        document_format = self._fallback_format_classification(filename)
        
        # Simple keyword-based business intent detection
        content_lower = content.lower()
        business_intent = "RFQ"  # Default
        
        if any(word in content_lower for word in ["complaint", "issue", "problem", "dissatisfied"]):
            business_intent = "Complaint"
        elif any(word in content_lower for word in ["invoice", "bill", "payment", "amount due"]):
            business_intent = "Invoice"
        elif any(word in content_lower for word in ["gdpr", "fda", "regulation", "compliance", "policy"]):
            business_intent = "Regulation"
        elif any(word in content_lower for word in ["fraud", "suspicious", "risk", "security"]):
            business_intent = "Fraud Risk"
        elif any(word in content_lower for word in ["quote", "rfq", "proposal", "pricing"]):
            business_intent = "RFQ"
        
        return {
            "document_format": document_format,
            "business_intent": business_intent,
            "confidence_score": 0.3,
            "reasoning": f"Fallback classification due to error: {error}",
            "key_indicators": ["fallback_rules", "filename_analysis"],
            "filename": filename,
            "timestamp": datetime.now().isoformat(),
            "content_length": len(content),
            "agent_type": "classifier",
            "model_used": "fallback",
            "error": error
        }
    
    def get_classification_schema(self) -> Dict[str, List[str]]:
        """Get the classification schema"""
        return {
            "format_types": self.format_types,
            "business_intents": self.business_intents
        }
