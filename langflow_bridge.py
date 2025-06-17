
from flask import Flask, Response, stream_with_context, request
import requests

app = Flask(__name__)

@app.route('/api/langflow/runs', methods=['POST'])
def langflow_runs():
    langflow_url = "http://langflow:7860/api/runs"
    data = request.get_json()
    
    def generate():
        with requests.post(langflow_url, json=data, stream=True) as r:
            for line in r.iter_lines():
                if line:
                    yield f"data: {line.decode('utf-8')}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')
