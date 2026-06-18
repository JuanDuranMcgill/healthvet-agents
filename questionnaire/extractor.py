import json
import os
import requests
from dotenv import load_dotenv

def extract_findings(report_text: str):
    load_dotenv()
    api_key = os.environ.get('FEATHERLESS_API_KEY')
    if not api_key:
        raise ValueError("FEATHERLESS_API_KEY is not set.")

    prompt = f"""You are an analytical extraction engine for a healthcare vendor vetting system.
Read the following concatenated agent reports and extract the findings into a structured JSON format.

For each of the following 9 categories, provide a score (0-10), evidence (brief quote or summary), and confidence (0.0 to 1.0). If no evidence is found for a category, set the score to 5, evidence to "No evidence found", and confidence to 0.0.

Categories:
1. patient_safety (clinical outcomes, safety evidence)
2. security_breach (breach history, OCR notifications, security posture)
3. regulatory_compliance (FDA clearance, ONC cert, HIPAA, SOC 2)
4. deployment_speed (time-to-value, implementation effort)
5. cost (pricing, total cost of ownership)
6. integration_interop (EHR fit, interoperability)
7. vendor_stability (litigation, financial/business stability)
8. support_service (support quality, SLAs, service)
9. data_transparency (data residency, subprocessor transparency)

Also, if you find any material negative or positive factors that do NOT fit into these 9 categories, list them in the `uncovered` array.

Respond EXACTLY with this JSON structure and no markdown formatting or other text:
{{
  "scores": {{
    "patient_safety": {{"score": 9, "evidence": "...", "confidence": 0.8}},
    ... (all 9 categories)
  }},
  "uncovered": [
    {{"factor": "...", "evidence": "...", "materiality": "high/medium/low"}}
  ]
}}

Agent Reports:
{report_text}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    req_data = {
        "model": "meta-llama/Meta-Llama-3-8B-Instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1500
    }
    resp = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json=req_data).json()
    
    if 'choices' not in resp:
        raise RuntimeError(f"API Error: {resp}")

    content = resp['choices'][0]['message']['content'].strip()
    
    # Clean up markdown if LLM includes it
    if content.startswith("```json"):
        content = content[7:-3]
    elif content.startswith("```"):
        content = content[3:-3]
        
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON. Raw content: {content}")
        raise e
