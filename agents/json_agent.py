import os
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import google.generativeai as genai

class JSONAgent:
    """
    JSON Agent for validating schema and detecting field/type mismatches.
    Uses Gemini 1.5 Flash for intelligent JSON analysis.
    """
    
    def __init__(self):
        """Initialize the JSON agent"""
        self.logger = logging.getLogger(__name__)
        
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY", "your-api-key-here")
        genai.configure(api_key=api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Define validation categories
        self.validation_types = ["Valid", "Invalid Syntax", "Schema Mismatch", "Type Error", "Missing Fields"]
        self.severity_levels = ["Low", "Medium", "High", "Critical"]
        
        self.analysis_prompt = self._build_analysis_prompt()
        
    def _build_analysis_prompt(self) -> str:
        """Build the JSON analysis prompt for Gemini"""
        return f"""
You are an expert JSON validator and schema analyzer. Analyze the provided JSON content and validate its structure:

1. SYNTAX VALIDATION: Check if JSON is syntactically valid
2. SCHEMA ANALYSIS: Identify data types and structure patterns
3. TYPE CONSISTENCY: Flag any type mismatches or inconsistencies
4. FIELD VALIDATION: Check for missing or unexpected fields

Validation Categories:
- Valid: Properly formatted JSON with consistent schema
- Invalid Syntax: JSON parsing errors, malformed structure
- Schema Mismatch: Inconsistent field structures across objects
- Type Error: Incorrect data types for fields
- Missing Fields: Required fields are absent

Severity Levels:
- Critical: JSON cannot be parsed or used
- High: Major schema violations that break functionality
- Medium: Type inconsistencies that may cause issues
- Low: Minor formatting or optional field issues

Respond ONLY with a valid JSON object in this exact format:
{{
    "is_valid_json": true,
    "validation_status": "one of the validation types",
    "severity": "one of the severity levels",
    "schema_analysis": {{
        "detected_fields": ["field1", "field2"],
        "field_types": {{"field1": "string", "field2": "number"}},
        "nested_levels": 2,
        "array_detected": true
    }},
    "errors_found": ["error1", "error2"],
    "type_mismatches": ["field with wrong type"],
    "missing_fields": ["expected but missing field"],
    "confidence_score": 0.95,
    "recommendations": ["suggestion1", "suggestion2"],
    "reasoning": "Brief explanation of validation results"
}}

JSON Content to Analyze:
"""

    def analyze_json(self, content: str, filename: str = "unknown") -> Dict[str, Any]:
        """
        Analyze JSON content for validation and schema consistency
        
        Args:
            content: The JSON content to analyze
            filename: The original filename (optional)
            
        Returns:
            Dictionary containing JSON analysis results
        """
        try:
            self.logger.info(f"Analyzing JSON: {filename}")
            
            # First, try basic JSON parsing
            basic_validation = self._basic_json_validation(content)
            
            # Prepare the full prompt
            full_prompt = self.analysis_prompt + f"\n\nFilename: {filename}\n\n{content[:4000]}"
            
            # Get analysis from Gemini
            response = self.model.generate_content(full_prompt)
            
            # Parse the response
            analysis_result = self._parse_gemini_response(response.text)
            
            # Merge basic validation with AI analysis
            analysis_result.update(basic_validation)
            
            # Add metadata
            analysis_result.update({
                "filename": filename,
                "timestamp": datetime.now().isoformat(),
                "content_length": len(content),
                "agent_type": "json",
                "model_used": "gemini-1.5-flash"
            })
            
            # Validate analysis
            validated_result = self._validate_analysis(analysis_result)
            
            self.logger.info(f"JSON analysis completed for {filename}: {validated_result['validation_status']}")
            
            return validated_result
            
        except Exception as e:
            self.logger.error(f"JSON analysis error for {filename}: {str(e)}")
            return self._create_fallback_analysis(content, filename, str(e))
    
    def _basic_json_validation(self, content: str) -> Dict[str, Any]:
        """Perform basic JSON validation"""
        try:
            parsed_json = json.loads(content)
            return {
                "is_valid_json": True,
                "parsed_content": parsed_json,
                "json_type": type(parsed_json).__name__
            }
        except json.JSONDecodeError as e:
            return {
                "is_valid_json": False,
                "json_error": str(e),
                "json_type": "invalid"
            }
    
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
        
        # Validate validation status
        if result.get("validation_status") not in self.validation_types:
            self.logger.warning(f"Invalid validation status: {result.get('validation_status')}")
            if result.get("is_valid_json"):
                result["validation_status"] = "Valid"
            else:
                result["validation_status"] = "Invalid Syntax"
        
        # Validate severity
        if result.get("severity") not in self.severity_levels:
            self.logger.warning(f"Invalid severity: {result.get('severity')}")
            result["severity"] = "Medium"  # Default fallback
        
        # Ensure confidence score is valid
        if not isinstance(result.get("confidence_score"), (int, float)) or not (0 <= result.get("confidence_score", 0) <= 1):
            result["confidence_score"] = 0.5
        
        # Ensure required fields exist
        if not result.get("schema_analysis"):
            result["schema_analysis"] = self._analyze_schema_fallback(result.get("parsed_content"))
        
        if not result.get("errors_found"):
            result["errors_found"] = []
        
        if not result.get("type_mismatches"):
            result["type_mismatches"] = []
        
        if not result.get("missing_fields"):
            result["missing_fields"] = []
        
        if not result.get("recommendations"):
            result["recommendations"] = ["Validate JSON structure", "Check data types"]
        
        if not result.get("reasoning"):
            result["reasoning"] = "JSON validation based on syntax and structure analysis"
        
        return result
    
    def _analyze_schema_fallback(self, parsed_content: Any) -> Dict[str, Any]:
        """Fallback schema analysis"""
        if not parsed_content:
            return {
                "detected_fields": [],
                "field_types": {},
                "nested_levels": 0,
                "array_detected": False
            }
        
        schema_info = {
            "detected_fields": [],
            "field_types": {},
            "nested_levels": 0,
            "array_detected": isinstance(parsed_content, list)
        }
        
        def analyze_object(obj, level=0):
            schema_info["nested_levels"] = max(schema_info["nested_levels"], level)
            
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key not in schema_info["detected_fields"]:
                        schema_info["detected_fields"].append(key)
                        schema_info["field_types"][key] = type(value).__name__
                    
                    if isinstance(value, (dict, list)):
                        analyze_object(value, level + 1)
            elif isinstance(obj, list) and obj:
                analyze_object(obj[0], level)
        
        analyze_object(parsed_content)
        return schema_info
    
    def _create_fallback_analysis(self, content: str, filename: str, error: str) -> Dict[str, Any]:
        """Create a fallback analysis when Gemini fails"""
        
        # Basic validation
        basic_validation = self._basic_json_validation(content)
        
        validation_status = "Invalid Syntax" if not basic_validation["is_valid_json"] else "Valid"
        severity = "Critical" if not basic_validation["is_valid_json"] else "Low"
        
        return {
            "is_valid_json": basic_validation["is_valid_json"],
            "validation_status": validation_status,
            "severity": severity,
            "schema_analysis": self._analyze_schema_fallback(basic_validation.get("parsed_content")),
            "errors_found": [basic_validation.get("json_error", "Analysis error")],
            "type_mismatches": [],
            "missing_fields": [],
            "confidence_score": 0.3,
            "recommendations": ["Check JSON syntax", "Validate structure"],
            "reasoning": f"Fallback analysis due to error: {error}",
            "filename": filename,
            "timestamp": datetime.now().isoformat(),
            "content_length": len(content),
            "agent_type": "json",
            "model_used": "fallback",
            "error": error
        }

    def simulate_api_response(self, validation_result: Dict[str, Any]) -> None:
        """Simulate API response for integration"""
        if validation_result.get("severity") in ["High", "Critical"]:
            print(f"POST /risk_alert - JSON validation failed: {validation_result['validation_status']}")
            print(f"Response: {{'alert_id': 'json_{datetime.now().strftime('%Y%m%d_%H%M%S')}', 'status': 'created'}}")

    def run_json_agent(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main function to run JSON agent analysis - LangFlow compatible
        
        Args:
            input_data: Dictionary containing 'content' and optional 'filename'
            
        Returns:
            JSON analysis results
        """
        content = input_data.get('content', '')
        filename = input_data.get('filename', 'unknown')
        
        result = self.analyze_json(content, filename)
        
        # Simulate API call for high severity issues
        self.simulate_api_response(result)
        
        return result