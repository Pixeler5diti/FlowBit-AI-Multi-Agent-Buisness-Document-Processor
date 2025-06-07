import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

class ActionRouter:
    """
    Action Router for triggering follow-up actions based on classified data.
    Routes documents to appropriate workflows and escalates when needed.
    """
    
    def __init__(self, memory_store):
        """Initialize the action router"""
        self.logger = logging.getLogger(__name__)
        self.memory_store = memory_store
        
        # Define action rules
        self.action_rules = {
            "email_rules": {
                "high_urgency": ["urgent", "critical", "emergency"],
                "angry_tone": ["angry", "frustrated"],
                "escalation_intents": ["complaint", "fraud risk"]
            },
            "json_rules": {
                "critical_errors": ["invalid syntax", "critical"],
                "schema_issues": ["schema mismatch", "type error"]
            },
            "pdf_rules": {
                "high_value": 10000.0,  # Invoice amounts above this trigger alerts
                "regulatory_keywords": ["gdpr", "fda", "hipaa", "sox"]
            }
        }
        
        self.logger.info("Action Router initialized")
    
    def route_document(self, classification_result: Dict[str, Any], specialized_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Route a document based on classification and specialized analysis
        
        Args:
            classification_result: Initial classification from ClassifierAgent
            specialized_result: Results from specialized agent (Email/JSON/PDF)
            
        Returns:
            Dictionary containing routing decisions and actions taken
        """
        try:
            self.logger.info(f"Routing document: {classification_result.get('filename', 'unknown')}")
            
            routing_result = {
                "document_id": classification_result.get("id"),
                "filename": classification_result.get("filename"),
                "document_format": classification_result.get("document_format"),
                "business_intent": classification_result.get("business_intent"),
                "timestamp": datetime.now().isoformat(),
                "actions_triggered": [],
                "escalations": [],
                "api_calls": [],
                "routing_decision": "processed"
            }
            
            # Route based on document format and specialized analysis
            if classification_result.get("document_format") == "Email":
                routing_result.update(self._route_email(classification_result, specialized_result))
            elif classification_result.get("document_format") == "JSON":
                routing_result.update(self._route_json(classification_result, specialized_result))
            elif classification_result.get("document_format") == "PDF":
                routing_result.update(self._route_pdf(classification_result, specialized_result))
            
            # Route based on business intent
            routing_result.update(self._route_by_intent(classification_result))
            
            # Log routing decision
            self.memory_store._add_trace_log("document_routed", {
                "filename": routing_result["filename"],
                "actions_count": len(routing_result["actions_triggered"]),
                "escalations_count": len(routing_result["escalations"]),
                "routing_decision": routing_result["routing_decision"]
            })
            
            self.logger.info(f"Document routed: {len(routing_result['actions_triggered'])} actions, {len(routing_result['escalations'])} escalations")
            
            return routing_result
            
        except Exception as e:
            self.logger.error(f"Routing error: {str(e)}")
            return self._create_fallback_routing(classification_result, str(e))
    
    def _route_email(self, classification_result: Dict[str, Any], email_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Route email-specific actions"""
        actions = []
        escalations = []
        api_calls = []
        
        if email_result:
            urgency = email_result.get("urgency_level", "").lower()
            tone = email_result.get("tone", "").lower()
            sender = email_result.get("sender_email", "unknown")
            
            # High urgency emails
            if urgency in ["high", "critical"]:
                actions.append({
                    "action_type": "priority_queue",
                    "reason": f"High urgency email from {sender}",
                    "priority": "high"
                })
                
                escalations.append({
                    "escalation_type": "urgent_email",
                    "target": "management",
                    "reason": f"Urgent email requires immediate attention"
                })
            
            # Angry tone handling
            if tone == "angry":
                actions.append({
                    "action_type": "customer_service_alert",
                    "reason": "Angry customer detected",
                    "priority": "high"
                })
                
                # Simulate CRM escalation
                api_calls.append(self._simulate_crm_escalation(email_result))
        
        return {
            "actions_triggered": actions,
            "escalations": escalations,
            "api_calls": api_calls
        }
    
    def _route_json(self, classification_result: Dict[str, Any], json_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Route JSON-specific actions"""
        actions = []
        escalations = []
        api_calls = []
        
        if json_result:
            is_valid = json_result.get("is_valid_json", True)
            severity = json_result.get("severity", "").lower()
            validation_status = json_result.get("validation_status", "").lower()
            
            # Critical JSON issues
            if not is_valid or severity == "critical":
                actions.append({
                    "action_type": "data_validation_alert",
                    "reason": "Critical JSON validation failure",
                    "priority": "critical"
                })
                
                escalations.append({
                    "escalation_type": "data_integrity",
                    "target": "data_team",
                    "reason": "JSON parsing or validation failed"
                })
                
                # Simulate risk alert
                api_calls.append(self._simulate_risk_alert(json_result))
            
            # Schema issues
            elif "schema" in validation_status or "type" in validation_status:
                actions.append({
                    "action_type": "schema_review",
                    "reason": "JSON schema inconsistencies detected",
                    "priority": "medium"
                })
        
        return {
            "actions_triggered": actions,
            "escalations": escalations,
            "api_calls": api_calls
        }
    
    def _route_pdf(self, classification_result: Dict[str, Any], pdf_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Route PDF-specific actions"""
        actions = []
        escalations = []
        api_calls = []
        
        if pdf_result:
            invoice_total = self._parse_amount(pdf_result.get("invoice_total", "0"))
            regulatory_keywords = pdf_result.get("regulatory_keywords_found", [])
            
            # High-value invoices
            if invoice_total > self.action_rules["pdf_rules"]["high_value"]:
                actions.append({
                    "action_type": "high_value_review",
                    "reason": f"Invoice amount ${invoice_total:,.2f} exceeds threshold",
                    "priority": "high"
                })
                
                escalations.append({
                    "escalation_type": "financial_review",
                    "target": "finance_team",
                    "reason": f"High-value invoice requires approval"
                })
            
            # Regulatory compliance
            if regulatory_keywords:
                actions.append({
                    "action_type": "compliance_review",
                    "reason": f"Regulatory keywords detected: {', '.join(regulatory_keywords)}",
                    "priority": "high"
                })
                
                escalations.append({
                    "escalation_type": "compliance_alert",
                    "target": "compliance_team",
                    "reason": "Document contains regulatory compliance requirements"
                })
                
                # Simulate risk alert for regulatory content
                api_calls.append(self._simulate_risk_alert(pdf_result))
        
        return {
            "actions_triggered": actions,
            "escalations": escalations,
            "api_calls": api_calls
        }
    
    def _route_by_intent(self, classification_result: Dict[str, Any]) -> Dict[str, Any]:
        """Route based on business intent"""
        actions = []
        escalations = []
        
        intent = classification_result.get("business_intent", "").lower()
        
        if intent == "complaint":
            actions.append({
                "action_type": "complaint_handling",
                "reason": "Customer complaint requires attention",
                "priority": "high"
            })
            
            escalations.append({
                "escalation_type": "customer_complaint",
                "target": "customer_service",
                "reason": "Complaint needs immediate response"
            })
        
        elif intent == "fraud risk":
            actions.append({
                "action_type": "fraud_investigation",
                "reason": "Potential fraud risk detected",
                "priority": "critical"
            })
            
            escalations.append({
                "escalation_type": "security_alert",
                "target": "security_team",
                "reason": "Fraud risk requires immediate investigation"
            })
        
        elif intent == "regulation":
            actions.append({
                "action_type": "regulatory_review",
                "reason": "Regulatory document requires compliance review",
                "priority": "medium"
            })
        
        return {
            "actions_triggered": actions,
            "escalations": escalations
        }
    
    def _simulate_crm_escalation(self, email_result: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate CRM escalation API call"""
        api_call = {
            "endpoint": "POST /crm/escalate",
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "sender_email": email_result.get("sender_email"),
                "urgency": email_result.get("urgency_level"),
                "tone": email_result.get("tone"),
                "escalation_reason": "Angry customer email detected"
            },
            "response": {
                "escalation_id": f"crm_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "status": "created",
                "assigned_to": "customer_service_team"
            }
        }
        
        print(f"POST /crm/escalate - Customer escalation created")
        print(f"Response: {api_call['response']}")
        
        return api_call
    
    def _simulate_risk_alert(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate risk alert API call"""
        api_call = {
            "endpoint": "POST /risk_alert",
            "timestamp": datetime.now().isoformat(),
            "payload": {
                "document_type": analysis_result.get("agent_type"),
                "risk_factors": analysis_result.get("regulatory_keywords_found", []),
                "severity": analysis_result.get("severity", "medium"),
                "alert_reason": "Regulatory compliance or data validation issue"
            },
            "response": {
                "alert_id": f"risk_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "status": "created",
                "assigned_to": "compliance_team"
            }
        }
        
        print(f"POST /risk_alert - Risk alert created")
        print(f"Response: {api_call['response']}")
        
        return api_call
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float"""
        try:
            # Remove currency symbols and commas
            cleaned = str(amount_str).replace('$', '').replace(',', '').replace('€', '').replace('£', '')
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0
    
    def _create_fallback_routing(self, classification_result: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Create fallback routing when errors occur"""
        return {
            "document_id": classification_result.get("id"),
            "filename": classification_result.get("filename", "unknown"),
            "document_format": classification_result.get("document_format", "unknown"),
            "business_intent": classification_result.get("business_intent", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "actions_triggered": [{
                "action_type": "manual_review",
                "reason": f"Routing error: {error}",
                "priority": "medium"
            }],
            "escalations": [{
                "escalation_type": "system_error",
                "target": "admin",
                "reason": "Action router encountered an error"
            }],
            "api_calls": [],
            "routing_decision": "fallback",
            "error": error
        }

    def trigger_action_router(self, classification_result: Dict[str, Any], specialized_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main function to trigger action router - LangFlow compatible
        
        Args:
            classification_result: Classification results from any agent
            specialized_result: Optional specialized agent results
            
        Returns:
            Routing decisions and actions
        """
        return self.route_document(classification_result, specialized_result)
