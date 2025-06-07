import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

class MemoryStore:
    """
    In-memory storage for classification results and system state.
    Acts as a simple key-value store for the multi-agent system.
    """
    
    def __init__(self):
        """Initialize the memory store"""
        self.logger = logging.getLogger(__name__)
        
        # Main storage dictionaries
        self.classifications = {}  # Classification results
        self.trace_logs = []       # System trace logs
        self.agent_states = {}     # Agent state information
        
        self.logger.info("Memory store initialized")
    
    def store_classification(self, classification_result: Dict[str, Any]) -> str:
        """
        Store a classification result and return a unique ID
        
        Args:
            classification_result: The classification result to store
            
        Returns:
            Unique ID for the stored result
        """
        result_id = str(uuid.uuid4())
        
        # Add storage metadata
        storage_entry = {
            "id": result_id,
            "stored_at": datetime.now().isoformat(),
            "result_type": "classification",
            **classification_result
        }
        
        self.classifications[result_id] = storage_entry
        
        # Log the storage action
        self._add_trace_log("classification_stored", {
            "result_id": result_id,
            "document_format": classification_result.get("document_format"),
            "business_intent": classification_result.get("business_intent"),
            "filename": classification_result.get("filename")
        })
        
        self.logger.info(f"Classification stored with ID: {result_id}")
        return result_id
    
    def get_classification(self, result_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a classification result by ID
        
        Args:
            result_id: The ID of the classification result
            
        Returns:
            Classification result or None if not found
        """
        result = self.classifications.get(result_id)
        
        if result:
            self.logger.debug(f"Retrieved classification: {result_id}")
        else:
            self.logger.warning(f"Classification not found: {result_id}")
        
        return result
    
    def get_all_classifications(self) -> Dict[str, Any]:
        """Get all stored classification results"""
        return {
            "total_count": len(self.classifications),
            "classifications": list(self.classifications.values())
        }
    
    def _add_trace_log(self, action: str, details: Dict[str, Any]):
        """Add an entry to the trace log"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "log_id": str(uuid.uuid4())
        }
        
        self.trace_logs.append(log_entry)
        self.logger.debug(f"Trace log added: {action}")
    
    def get_trace_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get trace logs
        
        Args:
            limit: Maximum number of logs to return (most recent first)
            
        Returns:
            List of trace log entries
        """
        logs = sorted(self.trace_logs, key=lambda x: x["timestamp"], reverse=True)
        
        if limit:
            logs = logs[:limit]
        
        return logs
    
    def store_agent_state(self, agent_name: str, state: Dict[str, Any]) -> None:
        """
        Store state information for an agent
        
        Args:
            agent_name: Name of the agent
            state: State information to store
        """
        self.agent_states[agent_name] = {
            "agent_name": agent_name,
            "state": state,
            "updated_at": datetime.now().isoformat()
        }
        
        self._add_trace_log("agent_state_updated", {
            "agent_name": agent_name,
            "state_keys": list(state.keys())
        })
        
        self.logger.debug(f"Agent state stored: {agent_name}")
    
    def get_agent_state(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Get state information for an agent
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent state or None if not found
        """
        return self.agent_states.get(agent_name)
    
    def clear_memory(self) -> None:
        """Clear all stored data"""
        self.classifications.clear()
        self.trace_logs.clear()
        self.agent_states.clear()
        
        self.logger.info("Memory store cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory store statistics"""
        return {
            "total_classifications": len(self.classifications),
            "total_trace_logs": len(self.trace_logs),
            "total_agent_states": len(self.agent_states),
            "memory_store_status": "active"
        }
