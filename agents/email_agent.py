import os
import json
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import google.generativeai as genai

class EmailAgent:
    """
    Email Agent for extracting sender, urgency, and tone from email documents.
    Uses Gemini 1.5 Flash for intelligent email analysis.
    """
    
    def __init__(self):
        """Initialize the email agent"""
        self.logger = logging.getLogger(__name__)
        
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")
        genai.configure(api_key=api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Define analysis schema
        self.urgency_levels = ["Low", "Medium", "High", "Critical"]
        self.tone_types = ["Professional", "Friendly", "Angry", "Neutral", "Urgent", "Formal"]
        
        self.analysis_prompt = self._build_analysis_prompt()
        
    def _build_analysis_prompt(self) -> str:
        """Build the email analysis prompt for Gemini"""
        return f"""
You are an expert email analyzer. Analyze the provided email content and extract key information:

1. SENDER INFORMATION: Extract sender name and email address
2. URGENCY LEVEL: Classify as one of: {', '.join(self.urgency_levels)}
3. TONE ANALYSIS: Classify tone as one of: {', '.join(self.tone_types)}

Analysis Guidelines:

URGENCY CLASSIFICATION:
- Critical: Immediate action required, emergency situations, system outages
- High: Important deadlines, escalations, time-sensitive requests
- Medium: Standard business requests, routine follow-ups
- Low: FYI messages, casual updates, non-urgent inquiries

TONE CLASSIFICATION:
- Professional: Business-like, formal language, proper etiquette
- Friendly: Warm, casual, personable communication
- Angry: Frustrated, complaint-oriented, negative sentiment
- Neutral: Matter-of-fact, straightforward, no emotional indicators
- Urgent: Demanding immediate attention, stressed language
- Formal: Very structured, official, ceremonial language

Respond ONLY with a valid JSON object in this exact format:
{{
    "sender_name": "extracted name or 'Unknown'",
    "sender_email": "extracted email or 'Unknown'",
    "urgency_level": "one of the urgency levels",
    "tone": "one of the tone types",
    "confidence_score": 0.95,
    "key_phrases": ["phrase1", "phrase2", "phrase3"],
    "reasoning": "Brief explanation of analysis"
}}

Email Content to Analyze:
"""

    def analyze_email(self, content: str, filename: str = "unknown") -> Dict[str, Any]:
        """
        Analyze email content for sender, urgency, and tone
        
        Args:
            content: The email content to analyze
            filename: The original filename (optional)
            
        Returns:
            Dictionary containing email analysis results
        """
        try:
            self.logger.info(f"Analyzing email: {filename}")
            
            # Prepare the full prompt
            full_prompt = self.analysis_prompt + f"\n\nFilename: {filename}\n\n{content[:3000]}"
            
            # Get analysis from Gemini
            response = self.model.generate_content(full_prompt)
            
            # Parse the response
            analysis_result = self._parse_gemini_response(response.text)
            
            # Add metadata
            analysis_result.update({
                "filename": filename,
                "timestamp": datetime.now().isoformat(),
                "content_length": len(content),
                "agent_type": "email",
                "model_used": "gemini-1.5-flash"
            })
            
            # Validate analysis
            validated_result = self._validate_analysis(analysis_result)
            
            self.logger.info(f"Email analysis completed for {filename}: {validated_result['urgency_level']} urgency, {validated_result['tone']} tone")
            
            return validated_result
            
        except Exception as e:
            self.logger.error(f"Email analysis error for {filename}: {str(e)}")
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
    
    def _validate_analysis(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize analysis results"""
        
        # Validate urgency level
        if result.get("urgency_level") not in self.urgency_levels:
            self.logger.warning(f"Invalid urgency level: {result.get('urgency_level')}")
            result["urgency_level"] = "Medium"  # Default fallback
        
        # Validate tone
        if result.get("tone") not in self.tone_types:
            self.logger.warning(f"Invalid tone: {result.get('tone')}")
            result["tone"] = "Neutral"  # Default fallback
        
        # Ensure confidence score is valid
        if not isinstance(result.get("confidence_score"), (int, float)) or not (0 <= result.get("confidence_score", 0) <= 1):
            result["confidence_score"] = 0.5
        
        # Ensure required fields exist
        if not result.get("sender_name"):
            result["sender_name"] = self._extract_sender_fallback(result.get("content", ""))
        
        if not result.get("sender_email"):
            result["sender_email"] = self._extract_email_fallback(result.get("content", ""))
        
        if not result.get("reasoning"):
            result["reasoning"] = "Email analysis based on content patterns"
        
        if not result.get("key_phrases"):
            result["key_phrases"] = ["email_analysis"]
        
        return result
    
    def _extract_sender_fallback(self, content: str) -> str:
        """Fallback sender extraction using regex"""
        # Look for "From:" headers
        from_match = re.search(r'From:\s*([^\n<]+)', content, re.IGNORECASE)
        if from_match:
            return from_match.group(1).strip()
        
        # Look for email signatures
        name_match = re.search(r'Best regards,\s*([^\n]+)', content, re.IGNORECASE)
        if name_match:
            return name_match.group(1).strip()
        
        return "Unknown"
    
    def _extract_email_fallback(self, content: str) -> str:
        """Fallback email extraction using regex"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_matches = re.findall(email_pattern, content)
        if email_matches:
            return email_matches[0]
        return "Unknown"
    
    def _create_fallback_analysis(self, content: str, filename: str, error: str) -> Dict[str, Any]:
        """Create a fallback analysis when Gemini fails"""
        
        # Simple rule-based fallback
        urgency_level = "Medium"  # Default
        tone = "Neutral"  # Default
        
        content_lower = content.lower()
        
        # Urgency detection
        if any(word in content_lower for word in ["urgent", "asap", "emergency", "critical", "immediate"]):
            urgency_level = "High"
        elif any(word in content_lower for word in ["fyi", "info", "update", "notice"]):
            urgency_level = "Low"
        
        # Tone detection
        if any(word in content_lower for word in ["angry", "frustrated", "unacceptable", "disappointed"]):
            tone = "Angry"
        elif any(word in content_lower for word in ["thanks", "appreciate", "kind", "friendly"]):
            tone = "Friendly"
        elif any(word in content_lower for word in ["urgent", "asap", "need", "must"]):
            tone = "Urgent"
        elif any(word in content_lower for word in ["formal", "official", "pursuant", "hereby"]):
            tone = "Formal"
        
        return {
            "sender_name": self._extract_sender_fallback(content),
            "sender_email": self._extract_email_fallback(content),
            "urgency_level": urgency_level,
            "tone": tone,
            "confidence_score": 0.3,
            "key_phrases": ["fallback_analysis"],
            "reasoning": f"Fallback analysis due to error: {error}",
            "filename": filename,
            "timestamp": datetime.now().isoformat(),
            "content_length": len(content),
            "agent_type": "email",
            "model_used": "fallback",
            "error": error
        }

    def run_email_agent(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main function to run email agent analysis - LangFlow compatible
        
        Args:
            input_data: Dictionary containing 'content' and optional 'filename'
            
        Returns:
            Email analysis results
        """
        content = input_data.get('content', '')
        filename = input_data.get('filename', 'unknown')
        
        return self.analyze_email(content, filename)