import json
import os
import time
import uuid
import http.cookies
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv
load_dotenv()

import auth_google
import web_integration

PORT = int(os.environ.get("PORT", "8000"))
WEB_DIR = os.path.join(os.path.dirname(__file__), 'web')

# Paths that never require authentication.
PUBLIC_PREFIXES = ('/auth/', '/login.html', '/api/me')
PUBLIC_EXACT = {'/favicon.ico'}
# Static asset extensions are public so the login page can load CSS/JS.
PUBLIC_EXTS = ('.css', '.js', '.png', '.jpg', '.svg', '.ico', '.woff', '.woff2', '.ttf')

# Active vetting tasks
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "org_name": "St. Jude Medical Center",
        "org_size": "large",
        "priority_speed": 3,
        "priority_clinical": 5,
        "priority_compliance": 5,
        "priority_security": 5,
        "priority_cost": 2,
        "req_fda": True,
        "req_soc2": True,
        "req_onc": False,
        "req_baa": True
    }

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=4)

hospital_config = load_config()

# Active vetting tasks
DB_FILE = os.path.join(os.path.dirname(__file__), 'db.json')

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

active_vettings = load_db()

class HealthVetHTTPHandler(SimpleHTTPRequestHandler):
    # ---- CORS (frontend on Vercel, backend here) ----
    def end_headers(self):
        origin = self.headers.get('Origin')
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Credentials', 'true')
            # Chrome Private Network Access: a public site (Vercel) calling a
            # private-network address (tailnet 100.x) is blocked without this.
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.send_header('Vary', 'Origin')
        # Always revalidate so updated HTML/JS (e.g. api-base.js) is never stale.
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    # ---- auth helpers ----
    def _session(self):
        cookie = http.cookies.SimpleCookie(self.headers.get('Cookie', ''))
        sid = cookie['hv_session'].value if 'hv_session' in cookie else None
        return auth_google.get_session(sid), sid

    def _send_json(self, obj, status=200, extra_headers=None):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode('utf-8'))

    def _redirect(self, location, extra_headers=None):
        self.send_response(302)
        self.send_header('Location', location)
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _is_public(self, path):
        if not auth_google.auth_enabled():
            return True
        if path in PUBLIC_EXACT or path == '/login.html':
            return True
        if any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return True
        if path.endswith(PUBLIC_EXTS):
            return True
        return False

    def _require_auth(self, path):
        """Return True if the request is allowed to proceed."""
        if self._is_public(path):
            return True
        session, _ = self._session()
        if session:
            return True
        # API calls get 401; page loads get redirected to the login page.
        if path.startswith('/api/'):
            self._send_json({"error": "unauthorized"}, status=401)
        else:
            self._redirect('/login.html')
        return False

    def translate_path(self, path):
        # Serve from the 'web' folder for root-level files
        parsed = urlparse(path)
        rel_path = parsed.path.lstrip('/')
        if not rel_path:
            rel_path = 'index.html'
        
        # Check if requested file is under 'web'
        target = os.path.join(WEB_DIR, rel_path)
        if os.path.exists(target):
            return target
            
        return super().translate_path(path)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if not self._require_auth(path):
            return

        # ---- auth routes ----
        if path == '/api/me':
            session, _ = self._session()
            active_slug = hospital_config.get('active_profile')
            onboarded = bool(active_slug and web_integration.load_profile(active_slug))
            self._send_json({
                "auth_enabled": auth_google.auth_enabled(),
                "authenticated": bool(session) or not auth_google.auth_enabled(),
                "email": session["email"] if session else None,
                "name": session["name"] if session else None,
                "picture": session["picture"] if session else None,
                "onboarded": onboarded,
            })
            return

        elif path == '/auth/google':
            if not auth_google.auth_enabled():
                self._redirect('/')
                return
            self._redirect(auth_google.build_auth_url())
            return

        elif path == '/auth/google/callback':
            query = parse_qs(parsed_url.query)
            code = query.get('code', [None])[0]
            state = query.get('state', [None])[0]
            if not code or not state:
                self._send_json({"error": "missing code/state"}, status=400)
                return
            sid, err = auth_google.exchange_code(code, state)
            if err:
                self._send_json({"error": err}, status=403)
                return
            cookie = (f"hv_session={sid}; Path=/; HttpOnly; SameSite=None; "
                      f"Secure; Max-Age={auth_google.SESSION_TTL}")
            # After login, return the user to the frontend (Vercel) if configured.
            dest = os.environ.get('FRONTEND_URL', '/')
            self._redirect(dest, extra_headers={'Set-Cookie': cookie})
            return

        elif path == '/auth/logout':
            _, sid = self._session()
            auth_google.destroy_session(sid)
            self._redirect('/login.html',
                           extra_headers={'Set-Cookie': 'hv_session=; Path=/; Max-Age=0'})
            return

        # ---- questionnaire routes ----
        elif path == '/api/questionnaire':
            self._send_json(web_integration.questionnaire_json())
            return

        elif path == '/api/profile':
            query = parse_qs(parsed_url.query)
            slug = query.get('slug', [hospital_config.get('active_profile', '')])[0]
            prof = web_integration.load_profile(slug) if slug else None
            self._send_json(web_integration.profile_to_dict(prof) if prof else {"profile": None})
            return

        if path == '/api/history':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            history = list(active_vettings.values())
            self.wfile.write(json.dumps(history).encode('utf-8'))
            
        elif path == '/api/vetting_status':
            query = parse_qs(parsed_url.query)
            task_id = query.get('task_id', [None])[0]
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            if task_id in active_vettings:
                task = active_vettings[task_id]
                vendor = task.get("vendor", "Unknown")
                
                # Live Band fetch
                from band.client.rest import RestClient
                
                from dotenv import load_dotenv
                load_dotenv()
                
                scout_key = os.environ.get("SCOUT_API_KEY")
                visible_steps = []
                is_running = task.get("status") == "running"
                
                if task.get("error_msg"):
                    visible_steps.append({"agent": "System", "message": task["error_msg"], "status": "error", "timestamp": task.get("start_time", time.time())})
                agent_keys = [
                    os.environ.get("SCOUT_API_KEY"),
                    os.environ.get("FORENSICS_API_KEY"),
                    os.environ.get("COMPLIANCE_API_KEY"),
                    os.environ.get("GAP_API_KEY"),
                    os.environ.get("RISK_API_KEY"),
                    os.environ.get("SYNTHESIS_API_KEY")
                ]
                
                try:
                    import requests
                    merged_data = {}
                    for key in agent_keys:
                        if key:
                            headers = {"x-api-key": key}
                            resp = requests.get(f"https://app.band.ai/api/v1/agent/chats/{task_id}/context", headers=headers)
                            if resp.status_code == 200:
                                for m in resp.json().get("data", []):
                                    merged_data[m.get('id')] = m
                    
                    data = list(merged_data.values())
                    # Sort by timestamp (assuming created_at exists, or just rely on id order if possible. Wait, Band API context returns ordered. Let's just sort by created_at string)
                    data.sort(key=lambda x: x.get('created_at', ''))
                    
                    for m in data:
                        text = m.get('content', str(m))
                        sender_id = m.get('sender_id')
                        
                        agent = "scout"
                        if sender_id == os.environ.get("FORENSICS_AGENT_ID"): agent = "forensics"
                        elif sender_id == os.environ.get("COMPLIANCE_AGENT_ID"): agent = "compliance"
                        elif sender_id == os.environ.get("GAP_AGENT_ID"): agent = "gap"
                        elif sender_id == os.environ.get("RISK_AGENT_ID"): agent = "risk"
                        elif sender_id == os.environ.get("SYNTHESIS_AGENT_ID"): agent = "synthesis"
                        elif sender_id == os.environ.get("SCOUT_AGENT_ID"): agent = "scout"
                        else: agent = "scout"
                        
                        # Filter out system or initial user messages if needed
                        if "Please run a full vendor assessment" not in text:
                            visible_steps.append({
                                "agent": agent,
                                "message": text,
                                "status": "done",
                                "timestamp": time.time()
                            })
                            
                            
                    if visible_steps and visible_steps[-1]["agent"] == "synthesis":
                        is_running = False
                        if task_id in active_vettings and active_vettings[task_id]["status"] == "running":
                            # Parse verdict and generate real scores using AI
                            report = visible_steps[-1]["message"]
                            
                            try:
                                prompt = f"Analyze this healthcare vendor assessment report. Provide a JSON response with EXACTLY these keys:\n'verdict': (must be EXACTLY 'APPROVE', 'REJECT', or 'ESCALATE'),\n'security': (integer 0-100),\n'clinical': (integer 0-100),\n'compliance': (integer 0-100),\n'speed': (integer 0-100),\n'cost': (integer 0-100),\n'overall': (integer 0-100).\nDo not output anything else but valid JSON.\n\nReport:\n{report}"
                                headers = {"Authorization": f"Bearer {os.environ.get('FEATHERLESS_API_KEY')}", "Content-Type": "application/json"}
                                req_data = {"model": "meta-llama/Meta-Llama-3-8B-Instruct", "messages": [{"role": "user", "content": prompt}], "max_tokens": 150}
                                resp = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json=req_data).json()
                                content = resp['choices'][0]['message']['content'].strip()
                                if content.startswith("```json"): content = content[7:-3]
                                if content.startswith("```"): content = content[3:]
                                parsed = json.loads(content.strip())
                                
                                verdict = parsed.get("verdict", "ESCALATE")
                                active_vettings[task_id]["scores"] = {
                                    "security": parsed.get("security", 70),
                                    "clinical": parsed.get("clinical", 70),
                                    "compliance": parsed.get("compliance", 70),
                                    "speed": parsed.get("speed", 70),
                                    "cost": parsed.get("cost", 70),
                                    "overall": parsed.get("overall", 70)
                                }
                            except Exception as e:
                                print("Scoring LLM error:", e)
                                verdict = "ESCALATE"
                                if "APPROVE" in report: verdict = "APPROVE"
                                elif "REJECT" in report: verdict = "REJECT"
                                active_vettings[task_id]["scores"] = {
                                    "security": 75, "clinical": 75, "compliance": 75, "speed": 75, "cost": 75, "overall": 75
                                }
                                
                            # --- Quantification pipeline: score against the active hospital profile ---
                            active_slug = hospital_config.get('active_profile')
                            if active_slug:
                                try:
                                    prof = web_integration.load_profile(active_slug)
                                    if prof:
                                        fit = web_integration.score_report(prof, report, vendor)
                                        active_vettings[task_id]["fit"] = fit
                                        # the quantified verdict is authoritative when a profile exists
                                        verdict = fit.get("verdict", verdict)
                                except Exception as e:
                                    print("Quantification scoring error:", e)

                            active_vettings[task_id]["status"] = "completed"
                            active_vettings[task_id]["verdict"] = verdict
                            
                            if verdict == "ESCALATE" and not active_vettings[task_id].get("auto_email_sent"):
                                active_vettings[task_id]["auto_email_sent"] = True
                                
                                def trigger_auto_outreach(v_name, r_text):
                                    print(f"Triggering auto outreach for {v_name}")
                                    try:
                                        # 1. Find Email
                                        from duckduckgo_search import DDGS
                                        import requests
                                        results = DDGS().text(f"{v_name} company security compliance contact email address", max_results=5)
                                        search_text = json.dumps(results)
                                        prompt = f"Based on the following search results for {v_name}, extract their support, compliance, or security contact email address. Return ONLY the email address and no other text. If you cannot find one, return 'security@{v_name.replace(' ', '').lower()}.com'.\n\nSearch Results: {search_text}"
                                        headers = {"Authorization": f"Bearer {os.environ.get('FEATHERLESS_API_KEY')}", "Content-Type": "application/json"}
                                        req_data = {"model": "meta-llama/Meta-Llama-3-8B-Instruct", "messages": [{"role": "user", "content": prompt}], "max_tokens": 50}
                                        resp = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json=req_data).json()
                                        email = resp['choices'][0]['message']['content'].strip()
                                        import re
                                        match = re.search(r'[\w\.-]+@[\w\.-]+', email)
                                        email = match.group(0) if match else f"security@{v_name.replace(' ', '').lower()}.com"
                                        
                                        # 2. Draft Email
                                        prompt_draft = f"Based on the following vendor assessment report for {v_name}, draft a short, professional email (3-4 sentences) to the vendor's security team ({email}) requesting the specific missing documents or clarifications mentioned in the 'Recommended Next Steps' or 'Key Risks'. Do not include placeholders, sign it as 'HealthVet Security Team'.\n\nReport: {r_text}"
                                        req_data_draft = {"model": "meta-llama/Meta-Llama-3-8B-Instruct", "messages": [{"role": "user", "content": prompt_draft}], "max_tokens": 150}
                                        resp_draft = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json=req_data_draft).json()
                                        draft_body = resp_draft['choices'][0]['message']['content'].strip()
                                        
                                        # 3. Send Email via SendGrid
                                        sendgrid_key = os.environ.get('SENDGRID_API_KEY')
                                        twilio_from = os.environ.get('TWILIO_EMAIL_FROM', 'noreply@healthvet.app')
                                        if sendgrid_key:
                                            import sendgrid
                                            from sendgrid.helpers.mail import Mail, Email, To, Content
                                            sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
                                            mail = Mail(Email(twilio_from), To(email), f"HealthVet Assessment Findings - {v_name}", Content("text/plain", draft_body))
                                            sg.client.mail.send.post(request_body=mail.get())
                                            print(f"Auto-outreach sent to {email} for {v_name}")
                                        else:
                                            print(f"Auto-outreach simulated (no SENDGRID_API_KEY) to {email} for {v_name}:\n{draft_body}")
                                            
                                    except Exception as e:
                                        print(f"Auto-outreach error for {v_name}: {e}")

                                import threading
                                threading.Thread(target=trigger_auto_outreach, args=(vendor, report), daemon=True).start()

                            save_db(active_vettings)
                        
                except Exception as e:
                    print(f"Band SDK Fetch Error: {e}")
                    
                status_to_return = active_vettings.get(task_id, {}).get("status", "running") if is_running else "completed"
                
                self.wfile.write(json.dumps({
                    "task_id": task_id,
                    "vendor": vendor,
                    "status": status_to_return,
                    "logs": visible_steps,
                    "hospital_config": hospital_config,
                    "scores": active_vettings.get(task_id, {}).get("scores", None),
                    "fit": active_vettings.get(task_id, {}).get("fit", None),
                    "auto_email_sent": active_vettings.get(task_id, {}).get("auto_email_sent", False)
                }).encode('utf-8'))
                return
            
        elif path == '/api/export_csv':
            import csv
            from io import StringIO
            
            si = StringIO()
            writer = csv.writer(si)
            writer.writerow(['Task ID', 'Vendor', 'Start Time', 'Status', 'Verdict', 'Error'])
            
            for task in sorted(active_vettings.values(), key=lambda x: x.get('start_time', 0), reverse=True):
                writer.writerow([
                    task.get('task_id', ''),
                    task.get('vendor', ''),
                    task.get('start_time', ''),
                    task.get('status', ''),
                    task.get('verdict', ''),
                    task.get('error_msg', '')
                ])
                
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv')
            self.send_header('Content-Disposition', 'attachment; filename="healthvet_export.csv"')
            self.end_headers()
            self.wfile.write(si.getvalue().encode('utf-8'))
            
        else:
            super().do_GET()

    def do_POST(self):
        global hospital_config
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if not self._require_auth(path):
            return

        if path == '/api/submit_questionnaire':
            content_length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(content_length).decode('utf-8'))
            try:
                profile = web_integration.build_profile(data)
                # mark this as the active profile used for vendor scoring
                hospital_config['active_profile'] = profile.slug
                if data.get('hospital'):
                    hospital_config['org_name'] = data['hospital']
                save_config(hospital_config)
                self._send_json({
                    "status": "success",
                    "profile": web_integration.profile_to_dict(profile),
                })
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, status=400)
            return

        if path == '/api/find_email':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            vendor = data.get('vendor', 'Unknown')
            
            try:
                from duckduckgo_search import DDGS
                results = DDGS().text(f"{vendor} company security compliance contact email address", max_results=5)
                search_text = json.dumps(results)
                
                from dotenv import load_dotenv
                
                import requests
                load_dotenv()
                
                prompt = f"Based on the following search results for {vendor}, extract their support, compliance, or security contact email address. Return ONLY the email address and no other text. If you cannot find one, return 'security@{vendor.replace(' ', '').lower()}.com'.\n\nSearch Results: {search_text}"
                
                headers = {
                    "Authorization": f"Bearer {os.environ.get('FEATHERLESS_API_KEY')}",
                    "Content-Type": "application/json"
                }
                req_data = {
                    "model": "meta-llama/Meta-Llama-3-8B-Instruct",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 50
                }
                resp = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json=req_data).json()
                email = resp['choices'][0]['message']['content'].strip()
                import re
                match = re.search(r'[\w\.-]+@[\w\.-]+', email)
                if match:
                    email = match.group(0)
                else:
                    email = f"security@{vendor.replace(' ', '').lower()}.com"
            except Exception as e:
                print("Find email error:", e)
                email = f"security@{vendor.replace(' ', '').lower()}.com"
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"email": email}).encode('utf-8'))
            
        elif path == '/api/send_outreach':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            to_email = data.get('to')
            body = data.get('body')
            vendor = data.get('vendor', 'Vendor')
            
            from dotenv import load_dotenv
            
            load_dotenv()
            
            sendgrid_key = os.environ.get('SENDGRID_API_KEY')
            twilio_from = os.environ.get('TWILIO_EMAIL_FROM', 'noreply@healthvet.app')
            
            success = False
            msg = "Email sent successfully."
            
            if not sendgrid_key:
                msg = "SENDGRID_API_KEY missing in .env, but simulated success for demo."
                success = True
            else:
                try:
                    import sendgrid
                    from sendgrid.helpers.mail import Mail, Email, To, Content
                    sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
                    mail = Mail(
                        Email(twilio_from),
                        To(to_email),
                        f"HealthVet Assessment Findings - {vendor}",
                        Content("text/plain", body)
                    )
                    response = sg.client.mail.send.post(request_body=mail.get())
                    success = str(response.status_code).startswith('2')
                    if not success:
                        msg = f"SendGrid error: {response.status_code}"
                except Exception as e:
                    success = False
                    msg = str(e)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "message": msg}).encode('utf-8'))

        elif path == '/api/save_config':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            hospital_config.update(data)
            save_config(hospital_config)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "config": hospital_config}).encode('utf-8'))
            
        elif path == '/api/start_vetting':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            vendor = data.get('vendor', 'Epic Systems')
            
            from band.client.rest import RestClient
            
            from dotenv import load_dotenv
            load_dotenv()
            scout_key = os.environ.get("SCOUT_API_KEY")
            
            task_id = str(uuid.uuid4())
            is_live = True
            
            forensics_key = os.environ.get("FORENSICS_API_KEY")
            
            if forensics_key:
                try:
                    client = RestClient(api_key=forensics_key, base_url="https://app.band.ai")
                    chat_resp = client.agent_api_chats.create_agent_chat(chat={})
                    chat_id = chat_resp.data.id
                    
                    agent_ids = [
                        os.environ.get("SCOUT_AGENT_ID"),
                        os.environ.get("COMPLIANCE_AGENT_ID"),
                        os.environ.get("GAP_AGENT_ID"),
                        os.environ.get("RISK_AGENT_ID"),
                        os.environ.get("SYNTHESIS_AGENT_ID")
                    ]
                    for aid in agent_ids:
                        if aid:
                            try:
                                from band.client.rest import ParticipantRequest
                                client.agent_api_participants.add_agent_chat_participant(chat_id, participant=ParticipantRequest(participant_id=aid))
                            except Exception as e:
                                print(f"Failed to add participant {aid}: {e}")
                                
                    scout_handle = os.environ.get("SCOUT_HANDLE", "@scout").lstrip("@")
                    scout_id = os.environ.get("SCOUT_AGENT_ID")
                    from band.client.rest import ChatMessageRequest, ChatMessageRequestMentionsItem
                    
                    # Agent Context Integration
                    h_cfg = hospital_config
                    ctx = f"Hospital Context: {h_cfg.get('org_name')} ({h_cfg.get('org_size')} size). Strict Requirements: SOC2={h_cfg.get('req_soc2')}, FDA={h_cfg.get('req_fda')}, BAA/HIPAA={h_cfg.get('req_baa')}. Priorities (1-5): Security {h_cfg.get('priority_security')}, Compliance {h_cfg.get('priority_compliance')}."
                    
                    client.agent_api_messages.create_agent_chat_message(chat_id, message=ChatMessageRequest(
                        content=f"@{scout_handle} Please run a full vendor assessment on {vendor}. {ctx}",
                        mentions=[ChatMessageRequestMentionsItem(id=scout_id, handle=scout_handle)]
                    ))
                    task_id = chat_id
                    is_live = True
                except Exception as e:
                    print(f"Band SDK Error during start_vetting: {e}")
                    # Force it into active_vettings with the error so the UI shows it
                    active_vettings[task_id] = {
                        "task_id": task_id,
                        "vendor": vendor,
                        "start_time": time.time(),
                        "status": "completed",
                        "results": None,
                        "error_msg": str(e)
                    }
            
            
            if not is_live and task_id not in active_vettings:
                active_vettings[task_id] = {
                    "task_id": task_id,
                    "vendor": vendor,
                    "start_time": time.time(),
                    "status": "completed",
                    "verdict": "UNKNOWN",
                    "error_msg": "Simulation fallback disabled."
                }
            elif is_live and task_id not in active_vettings:
                active_vettings[task_id] = {
                    "task_id": task_id,
                    "vendor": vendor,
                    "start_time": time.time(),
                    "status": "running",
                    "verdict": "PENDING"
                }
            save_db(active_vettings)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"task_id": task_id, "vendor": vendor, "is_live": is_live}).encode('utf-8'))
            
        elif path == '/api/delete_task':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            task_id = data.get('task_id')
            if task_id in active_vettings:
                del active_vettings[task_id]
                save_db(active_vettings)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
            
        elif path == '/api/extract_pros_cons':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            report_text = data.get('report', '')
            
            try:
                from dotenv import load_dotenv
                
                import requests
                load_dotenv()
                prompt = f"Based on the following vendor assessment report, extract exactly 3 short bullet points for 'Pros' and 3 short bullet points for 'Cons' regarding the vendor. Format as JSON: {{\"pros\": [\"pro1\", \"pro2\", \"pro3\"], \"cons\": [\"con1\", \"con2\", \"con3\"]}}. Do not include markdown blocks or any other text.\n\nReport: {report_text}"
                headers = {"Authorization": f"Bearer {os.environ.get('FEATHERLESS_API_KEY')}", "Content-Type": "application/json"}
                req_data = {"model": "meta-llama/Meta-Llama-3-8B-Instruct", "messages": [{"role": "user", "content": prompt}], "max_tokens": 150}
                resp = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json=req_data).json()
                
                content = resp['choices'][0]['message']['content'].strip()
                if content.startswith("```json"):
                    content = content[7:-3]
                parsed = json.loads(content)
            except Exception as e:
                print("Pros/Cons AI error:", e)
                parsed = {"pros": ["Live assessment completed.", "Refer to full report."], "cons": ["Refer to full report."]}
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(parsed).encode('utf-8'))
            
        elif path == '/api/clinical_insights':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            vendor = data.get('vendor', 'Unknown')
            verdict = data.get('verdict', 'REJECT')
            report_text = data.get('report', '')
            
            try:
                from dotenv import load_dotenv
                
                import requests
                load_dotenv()
                
                prompt = f"The healthcare vendor '{vendor}' received a verdict of {verdict}. Provide a JSON response with these keys EXACTLY:\n'tldr': A 2-sentence summary specifically written for a Chief Medical Officer.\n'alternatives': A list of exactly 3 strings containing names of alternative healthcare vendors in this space.\n'phi_risk': Either 'Low', 'Medium', or 'High'.\n\nReport:\n{report_text}"
                headers = {"Authorization": f"Bearer {os.environ.get('FEATHERLESS_API_KEY')}", "Content-Type": "application/json"}
                req_data = {"model": "meta-llama/Meta-Llama-3-8B-Instruct", "messages": [{"role": "user", "content": prompt}], "max_tokens": 200}
                resp = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json=req_data).json()
                
                content = resp['choices'][0]['message']['content'].strip()
                if content.startswith("```json"): content = content[7:-3]
                if content.startswith("```"): content = content[3:]
                parsed = json.loads(content.strip())
            except Exception as e:
                print("Insights error:", e)
                parsed = {"tldr": "Assessment completed. Please review full report.", "alternatives": ["Epic", "Cerner", "Athenahealth"], "phi_risk": "Medium"}
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(parsed).encode('utf-8'))
            
        elif path == '/api/vendor_chat':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            vendor = data.get('vendor', '')
            report_text = data.get('report', '')
            user_msg = data.get('message', '')
            
            try:
                from dotenv import load_dotenv
                
                import requests
                load_dotenv()
                
                system_prompt = f"You are a healthcare compliance expert assisting a doctor. You have just audited the vendor '{vendor}'. Use the following assessment report to answer the user's question concisely. Be brief and professional.\n\nReport:\n{report_text}"
                headers = {"Authorization": f"Bearer {os.environ.get('FEATHERLESS_API_KEY')}", "Content-Type": "application/json"}
                req_data = {"model": "meta-llama/Meta-Llama-3-8B-Instruct", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}], "max_tokens": 300}
                resp = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json=req_data).json()
                
                content = resp['choices'][0]['message']['content'].strip()
            except Exception as e:
                print("Chat error:", e)
                content = "Sorry, the AI chat service is currently unavailable."
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"response": content}).encode('utf-8'))
            
        elif path == '/api/compare':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            task_a = data.get('task_a')
            task_b = data.get('task_b')
            
            vendor_a = active_vettings.get(task_a, {})
            vendor_b = active_vettings.get(task_b, {})
            
            try:
                from dotenv import load_dotenv
                import requests
                load_dotenv()
                
                prompt = f"Compare two healthcare vendors based on their overall security, clinical, and compliance profiles. Vendor A is '{vendor_a.get('vendor')}' (Verdict: {vendor_a.get('verdict')}). Vendor B is '{vendor_b.get('vendor')}' (Verdict: {vendor_b.get('verdict')}). Provide a 2-3 sentence final recommendation on which vendor is superior and why. Return exactly this JSON: {{\"winner\": \"Name of winning vendor\", \"justification\": \"Your 2-3 sentence explanation\"}}"
                headers = {"Authorization": f"Bearer {os.environ.get('FEATHERLESS_API_KEY')}", "Content-Type": "application/json"}
                req_data = {"model": "meta-llama/Meta-Llama-3-8B-Instruct", "messages": [{"role": "user", "content": prompt}], "max_tokens": 200}
                resp = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json=req_data).json()
                
                content = resp['choices'][0]['message']['content'].strip()
                if content.startswith("```json"): content = content[7:-3]
                if content.startswith("```"): content = content[3:]
                parsed = json.loads(content.strip())
            except Exception as e:
                print("Compare error:", e)
                parsed = {"winner": "Tie", "justification": "Both vendors have unique strengths. Please review individual reports."}
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                "winner": parsed.get("winner", "Unknown"),
                "justification": parsed.get("justification", "Comparison failed."),
                "vendor_a": {"name": vendor_a.get("vendor"), "scores": vendor_a.get("scores", {})},
                "vendor_b": {"name": vendor_b.get("vendor"), "scores": vendor_b.get("scores", {})}
            }).encode('utf-8'))

        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    # Make sure web folder exists
    os.makedirs(WEB_DIR, exist_ok=True)
    
    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, HealthVetHTTPHandler)
    print(f"\n=========================================")
    print(f"HealthVet Doctor Dashboard Server Running")
    print(f"URL: http://localhost:{PORT}")
    print(f"Serving web resources from: {WEB_DIR}")
    print(f"Press Ctrl+C to exit")
    print(f"=========================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web server...")
        httpd.server_close()

if __name__ == '__main__':
    run_server()
