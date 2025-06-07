# Multi-Format Autonomous AI Agent System

**An intelligent workflow orchestrator** that processes emails, PDFs, and JSON inputs, classifies their intent, and triggers context-aware actions.

![System Diagram](assets/system-sketch.png) *[Use Napkin-style diagram here]*

## 🚀 Key Features
- **Smart Classification**  
  Detects document format (Email/PDF/JSON) + business intent (RFQ/Complaint/Invoice etc.)
- **Specialized Agents**  
  - Email: Extracts sender, urgency, and tone (escalation detection)  
  - PDF: Flags high-value invoices & regulatory keywords  
  - JSON: Schema validation + anomaly detection  
- **Action Chaining**  
  Auto-triggers CRM alerts, risk flags, or summaries via API  
- **Production-Ready**  
  Dockerized with Redis memory store and audit logging  

## 🛠️ Tech Stack
- **Core**: Python + FastAPI  
- **AI Orchestration**: LangFlow  
- **Memory**: Redis  
- **Frontend**: Next.js + shadcn/ui  
- **PDF Parsing**: PyPDF2  

## 📦 Installation
1. Clone repo:
   ```bash
   git clone https://github.com/Pixeler5diti/FlowBit-AI-Multi-Agent-Buisness-Document-Processor
   ```
