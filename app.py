import os
import json
import logging
import threading
import time
from flask import Flask, render_template, request, flash, redirect, url_for, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
import traceback

from agents.classifier import ClassifierAgent
from agents.email_agent import EmailAgent
from agents.json_agent import JSONAgent
from agents.pdf_agent import PDFAgent
from agents.action_router import ActionRouter
from memory_store import MemoryStore

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'json', 'eml', 'msg'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize components
memory_store = MemoryStore()
classifier_agent = ClassifierAgent()
email_agent = EmailAgent()
json_agent = JSONAgent()
pdf_agent = PDFAgent()
action_router = ActionRouter(memory_store)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Main page with upload form"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and classification"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('index'))
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('index'))
        
        if not allowed_file(file.filename):
            flash('File type not allowed. Please upload: txt, pdf, json, eml, msg files', 'error')
            return redirect(url_for('index'))
        
        # Save uploaded file
        filename = secure_filename(file.filename or 'unknown')
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Read file content
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try reading as binary for PDFs and convert to string
            with open(filepath, 'rb') as f:
                content = str(f.read())
        
        # Step 1: Classify the document
        classification_result = classifier_agent.classify_document(content, filename)
        
        # Step 2: Run specialized agent based on format
        specialized_result = None
        document_format = classification_result.get('document_format', '').lower()
        
        if document_format == 'email':
            specialized_result = email_agent.analyze_email(content, filename)
        elif document_format == 'json':
            specialized_result = json_agent.analyze_json(content, filename)
        elif document_format == 'pdf':
            specialized_result = pdf_agent.analyze_pdf(content, filename)
        
        # Step 3: Route actions
        routing_result = action_router.route_document(classification_result, specialized_result)
        
        # Store all results in memory
        result_id = memory_store.store_classification({
            **classification_result,
            'specialized_analysis': specialized_result,
            'routing_decisions': routing_result
        })
        
        # Clean up uploaded file
        os.remove(filepath)
        
        flash('Document classified successfully!', 'success')
        return redirect(url_for('view_results', result_id=result_id))
        
    except Exception as e:
        app.logger.error(f"Error processing upload: {str(e)}")
        app.logger.error(traceback.format_exc())
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/results/<result_id>')
def view_results(result_id):
    """Display classification results"""
    try:
        result = memory_store.get_classification(result_id)
        if not result:
            flash('Results not found', 'error')
            return redirect(url_for('index'))
        
        return render_template('results.html', result=result, result_id=result_id)
        
    except Exception as e:
        app.logger.error(f"Error retrieving results: {str(e)}")
        flash('Error retrieving results', 'error')
        return redirect(url_for('index'))

@app.route('/api/classify', methods=['POST'])
def api_classify():
    """API endpoint for classification"""
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({'error': 'Content is required'}), 400
        
        content = data['content']
        filename = data.get('filename', 'unknown')
        
        # Classify the document
        classification_result = classifier_agent.classify_document(content, filename)
        
        # Store result in memory
        result_id = memory_store.store_classification(classification_result)
        
        return jsonify({
            'result_id': result_id,
            'classification': classification_result
        })
        
    except Exception as e:
        app.logger.error(f"API classification error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/results/<result_id>')
def api_get_results(result_id):
    """API endpoint to get classification results"""
    try:
        result = memory_store.get_classification(result_id)
        if not result:
            return jsonify({'error': 'Results not found'}), 404
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"API get results error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/memory')
def view_memory():
    """Debug endpoint to view memory store contents"""
    return jsonify(memory_store.get_all_classifications())

@app.route('/api/logs')
def api_get_logs():
    """API endpoint to get trace logs"""
    try:
        limit = request.args.get('limit', 50, type=int)
        logs = memory_store.get_trace_logs(limit=limit)
        return jsonify({
            'logs': logs,
            'total_count': len(logs)
        })
    except Exception as e:
        app.logger.error(f"Error retrieving logs: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/dashboard')
def dashboard():
    """Dashboard page showing system overview"""
    try:
        stats = memory_store.get_statistics()
        recent_logs = memory_store.get_trace_logs(limit=10)
        return render_template('dashboard.html', stats=stats, logs=recent_logs)
    except Exception as e:
        app.logger.error(f"Dashboard error: {str(e)}")
        flash('Error loading dashboard', 'error')
        return redirect(url_for('index'))

def get_logs():
    """Helper function for LangFlow compatibility"""
    return memory_store.get_trace_logs()

def run_email_agent(input_data):
    """LangFlow compatible email agent function"""
    return email_agent.run_email_agent(input_data)

def run_json_agent(input_data):
    """LangFlow compatible JSON agent function"""  
    return json_agent.run_json_agent(input_data)

def run_pdf_agent(input_data):
    """LangFlow compatible PDF agent function"""
    return pdf_agent.run_pdf_agent(input_data)

def trigger_action_router(classification_result, specialized_result=None):
    """LangFlow compatible action router function"""
    return action_router.trigger_action_router(classification_result, specialized_result)

# LangFlow Integration Endpoints
@app.route('/api/langflow/runs', methods=['GET'])
def get_langflow_runs():
    """Get all workflow runs"""
    try:
        classifications = memory_store.get_all_classifications()
        runs = []
        
        for classification in classifications['classifications']:
            run_data = {
                "id": classification.get("id"),
                "flow_id": "classifier-agent-flow",
                "status": "completed" if not classification.get("error") else "failed",
                "created_at": classification.get("timestamp"),
                "updated_at": classification.get("timestamp"),
                "inputs": {
                    "content": classification.get("content", "")[:100] + "..." if len(classification.get("content", "")) > 100 else classification.get("content", ""),
                    "filename": classification.get("filename")
                },
                "outputs": {
                    "document_format": classification.get("document_format"),
                    "business_intent": classification.get("business_intent"),
                    "confidence_score": classification.get("confidence_score")
                },
                "execution_time": 2.5,  # Simulated
                "error": classification.get("error")
            }
            runs.append(run_data)
        
        return jsonify({
            "runs": runs,
            "total": len(runs)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/langflow/runs/<run_id>', methods=['GET'])
def get_langflow_run(run_id):
    """Get specific workflow run details"""
    try:
        result = memory_store.get_classification(run_id)
        if not result:
            return jsonify({"error": "Run not found"}), 404
        
        run_detail = {
            "id": run_id,
            "flow_id": "classifier-agent-flow",
            "status": "completed" if not result.get("error") else "failed",
            "created_at": result.get("timestamp"),
            "updated_at": result.get("timestamp"),
            "inputs": {
                "content": result.get("content", ""),
                "filename": result.get("filename")
            },
            "outputs": {
                "document_format": result.get("document_format"),
                "business_intent": result.get("business_intent"),
                "confidence_score": result.get("confidence_score"),
                "reasoning": result.get("reasoning"),
                "key_indicators": result.get("key_indicators")
            },
            "specialized_analysis": result.get("specialized_analysis"),
            "routing_decisions": result.get("routing_decisions"),
            "execution_time": 2.5,
            "error": result.get("error"),
            "logs": [
                {
                    "timestamp": result.get("timestamp"),
                    "level": "INFO",
                    "message": f"Document classified as {result.get('document_format')} / {result.get('business_intent')}"
                }
            ]
        }
        
        return jsonify(run_detail)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/langflow/runs/<run_id>/stream', methods=['GET'])
def stream_langflow_run(run_id):
    """Stream workflow execution logs via SSE"""
    def generate():
        result = memory_store.get_classification(run_id)
        if not result:
            yield f"data: {json.dumps({'error': 'Run not found'})}\n\n"
            return
        
        # Simulate streaming execution logs
        logs = [
            {"timestamp": result.get("timestamp"), "level": "INFO", "message": "Starting document classification"},
            {"timestamp": result.get("timestamp"), "level": "INFO", "message": f"Processing file: {result.get('filename')}"},
            {"timestamp": result.get("timestamp"), "level": "INFO", "message": f"Format detected: {result.get('document_format')}"},
            {"timestamp": result.get("timestamp"), "level": "INFO", "message": f"Intent classified: {result.get('business_intent')}"},
            {"timestamp": result.get("timestamp"), "level": "INFO", "message": "Classification completed successfully"}
        ]
        
        for log in logs:
            yield f"data: {json.dumps(log)}\n\n"
        
        yield f"data: {json.dumps({'status': 'completed'})}\n\n"
    
    return app.response_class(generate(), mimetype='text/plain')

@app.route('/api/trigger', methods=['POST'])
def trigger_workflow():
    """Trigger workflow execution"""
    try:
        data = request.get_json()
        flow_id = data.get('flow_id')
        inputs = data.get('inputs', {})
        trigger_type = data.get('trigger_type', 'manual')
        
        content = inputs.get('content', '')
        filename = inputs.get('filename', 'api_triggered')
        
        if not content:
            return jsonify({"error": "Content is required"}), 400
        
        # Execute the appropriate workflow
        if flow_id == 'email-agent-flow':
            result = email_agent.analyze_email(content, filename)
        elif flow_id == 'json-agent-flow':
            result = json_agent.analyze_json(content, filename)
        elif flow_id == 'pdf-agent-flow':
            result = pdf_agent.analyze_pdf(content, filename)
        elif flow_id == 'classifier-agent-flow':
            # Full classification pipeline
            classification_result = classifier_agent.classify_document(content, filename)
            
            # Run specialized agent
            specialized_result = None
            document_format = classification_result.get('document_format', '').lower()
            
            if document_format == 'email':
                specialized_result = email_agent.analyze_email(content, filename)
            elif document_format == 'json':
                specialized_result = json_agent.analyze_json(content, filename)
            elif document_format == 'pdf':
                specialized_result = pdf_agent.analyze_pdf(content, filename)
            
            # Route actions
            routing_result = action_router.route_document(classification_result, specialized_result)
            
            # Store complete result
            result = {
                **classification_result,
                'specialized_analysis': specialized_result,
                'routing_decisions': routing_result
            }
        else:
            return jsonify({"error": "Unknown flow_id"}), 400
        
        # Store result
        result_id = memory_store.store_classification(result)
        
        return jsonify({
            "run_id": result_id,
            "status": "completed",
            "outputs": result
        })
        
    except Exception as e:
        app.logger.error(f"Workflow trigger error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/hooks/<workflow_id>', methods=['GET'])
def get_webhook_info(workflow_id):
    """Get webhook information for a workflow"""
    webhook_url = f"{request.url_root}api/trigger"
    
    return jsonify({
        "webhook_url": webhook_url,
        "workflow_id": workflow_id,
        "method": "POST",
        "headers": {
            "Content-Type": "application/json"
        },
        "payload_example": {
            "flow_id": workflow_id,
            "trigger_type": "webhook",
            "inputs": {
                "content": "Document content here",
                "filename": "document.txt"
            }
        }
    })

@app.route('/api/flows', methods=['GET'])
def get_available_flows():
    """Get list of available flows"""
    flows = [
        {
            "id": "classifier-agent-flow",
            "name": "Document Classifier Agent",
            "description": "Multi-agent document classification system",
            "trigger_types": ["manual", "webhook", "cron"]
        },
        {
            "id": "email-agent-flow", 
            "name": "Email Agent",
            "description": "Analyzes email content for sender, urgency, and tone",
            "trigger_types": ["manual", "webhook", "cron"]
        },
        {
            "id": "json-agent-flow",
            "name": "JSON Agent", 
            "description": "Validates JSON schema and detects type mismatches",
            "trigger_types": ["manual", "webhook", "cron"]
        },
        {
            "id": "pdf-agent-flow",
            "name": "PDF Agent",
            "description": "Extracts invoice totals and detects regulatory keywords", 
            "trigger_types": ["manual", "webhook", "cron"]
        }
    ]
    
    return jsonify({"flows": flows})

# Cron Scheduling System
class CronScheduler:
    def __init__(self):
        self.scheduled_jobs = {}
        self.running = False
        
    def start(self):
        """Start the cron scheduler"""
        self.running = True
        threading.Thread(target=self._run_scheduler, daemon=True).start()
        
    def _run_scheduler(self):
        """Run scheduled jobs"""
        while self.running:
            current_time = time.time()
            for job_id, job in list(self.scheduled_jobs.items()):
                if current_time >= job['next_run']:
                    try:
                        # Execute the job
                        if job['flow_id'] == 'classifier-agent-flow':
                            # Example: Process files from a directory
                            for filename in os.listdir('test_documents'):
                                if filename.endswith(('.txt', '.json')):
                                    filepath = os.path.join('test_documents', filename)
                                    with open(filepath, 'r') as f:
                                        content = f.read()
                                    
                                    # Trigger classification
                                    classification_result = classifier_agent.classify_document(content, filename)
                                    memory_store.store_classification(classification_result)
                        
                        # Update next run time
                        job['next_run'] = current_time + job['interval']
                        
                    except Exception as e:
                        app.logger.error(f"Cron job {job_id} failed: {str(e)}")
            
            time.sleep(10)  # Check every 10 seconds
    
    def schedule_job(self, job_id, flow_id, interval):
        """Schedule a new cron job"""
        self.scheduled_jobs[job_id] = {
            'flow_id': flow_id,
            'interval': interval,
            'next_run': time.time() + interval
        }

# Initialize cron scheduler
cron_scheduler = CronScheduler()

@app.route('/api/cron/schedule', methods=['POST'])
def schedule_cron_job():
    """Schedule a cron job"""
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        flow_id = data.get('flow_id')
        interval = data.get('interval', 3600)  # Default 1 hour
        
        cron_scheduler.schedule_job(job_id, flow_id, interval)
        
        return jsonify({
            "job_id": job_id,
            "status": "scheduled",
            "interval": interval
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cron/jobs', methods=['GET'])
def get_cron_jobs():
    """Get all scheduled cron jobs"""
    return jsonify({"jobs": cron_scheduler.scheduled_jobs})

if __name__ == '__main__':
    # Start cron scheduler
    cron_scheduler.start()
    app.run(host='0.0.0.0', port=5000, debug=True)
