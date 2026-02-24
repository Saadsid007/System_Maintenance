import json
import time
import os
import requests # Used only for GitHub API (Gist Sync)
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
    print(" [SYS_ERR] Critical module 'curl_cffi' missing.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SYSTEM] %(message)s')
logger = logging.getLogger(__name__)

# Indian Standard Time (IST) setup
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist():
    """Returns current time in IST formatted string"""
    return datetime.now(IST).strftime('%H:%M:%S.%f')[:-3]

# Polymorphic Fingerprints (Rotating Identities)
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
        self.MAX_DURATION = 21000 # ~6 hours safe limit
        
        # --- Multi-Threading Safety ---
        self.sessions = []
        self.lock = threading.Lock()
        self.keep_data = []
        self.consecutive_errors = 0
        self.corruption_detected = False
        self.global_pause = False # Flag to halt operations if Akamai WAF triggers

        if not self.log_id or not self.api_key:
            print(f"[{get_ist()}]  [SYS_ERR] Config (ID/KEY) missing. Aborting.")
            sys.exit(1)

    def _d(self, s):
        """Decrypts Base64 Strings"""
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
            
        # --- Create High-Speed Pre-warmed Session Pool (Increased to 100 for safety) ---
        for _ in range(100): 
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
            print(f"[{get_ist()}]  [CLOUD_ERR] Sync Failed: {e}")
            return [], ""

    def update_logs(self, valid_list, filename):
        headers = {"Authorization": f"token {self.api_key}"}
        new_content = "\n".join(valid_list)
        payload = {"files": {filename: {"content": new_content}}}
        try:
            requests.patch(f"https://api.github.com/gists/{self.log_id}", json=payload, headers=headers)
            print(f"[{get_ist()}]  [CLOUD_SYNC] Database optimized & cleaned.")
        except: pass

    # --- TURBO CHECK ENGINE (curl_cffi) ---
    def ping_endpoint(self, code):
        url = self._d("aHR0cHM6Ly93d3cuc2hlaW5pbmRpYS5pbi9hcGkvY2FydC9hcHBseS12b3VjaGVy")
        payload = {"voucherId": code, "device": {"client_type": "web"}}
        
        # Pick a random pre-configured session
        session = random.choice(self.sessions)
        
        try:
            resp = session.post(url, json=payload, timeout=8)
            
            # 403 Block protection
            if resp.status_code in [403, 429]:
                return {"status_code": resp.status_code}
                
            return resp.json()
        except Exception:
            return None

    def reset_endpoint(self, code):
        """ Runs in background. Added delay so it doesn't overlap with active checks and trigger DDoS blocks. """
        time.sleep(random.uniform(2.0, 4.0)) # Wait before resetting to prevent hitting rate limits
        
        url = self._d("aHR0cHM6Ly93d3cuc2hlaW5pbmRpYS5pbi9hcGkvY2FydC9yZXNldC12b3VjaGVy")
        payload = {"voucherId": code, "device": {"client_type": "web"}}
        session = random.choice(self.sessions)
        try:
            session.post(url, json=payload, timeout=3) 
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
        """ Multi-threaded worker for checking coupons safely """
        masked = item[:3] + "*****" 
        
        # 1. Global WAF Pause check with Wake-up Jitter
        if self.global_pause:
            time.sleep(5 + random.uniform(0.1, 2.0)) # Staggered wake-up so they don't fire all at once
            
        with self.lock:
            if self.consecutive_errors >= 4: 
                self.global_pause = True
                print(f"[{get_ist()}]  [🛡️ WAF ALERT] Server blocked us. Initiating 5s stealth cooldown...")
                time.sleep(5)
                self.consecutive_errors = 0
                self.global_pause = False

        # 2. Micro-delay to avoid triggering rate limits
        time.sleep(random.uniform(0.1, 0.3))

        resp = self.ping_endpoint(item)
        status = self.analyze_signal(resp)
        
        # Thread-Safe append to ensure NO COUPONS ARE LOST
        with self.lock:
            ts_end = get_ist()
            if status == "OK":
                print(f"[{ts_end}]    [OK] Verified: {masked}")
                self.trigger_background_reset(item) 
                self.keep_data.append(item)
                self.consecutive_errors = max(0, self.consecutive_errors - 1) 
            
            elif status == "ARCHIVED":
                print(f"[{ts_end}]    [WARN] Archived: {masked}")
                self.trigger_background_reset(item) 
                self.keep_data.append(item)
                self.consecutive_errors = max(0, self.consecutive_errors - 1)
            
            elif status == "CORRUPT":
                print(f"[{ts_end}]    [ERR] Corrupt Data: {masked} -> Purging")
                self.corruption_detected = True 
            
            elif status == "AUTH_FAIL":
                print(f"[{ts_end}]  [CRITICAL] Session Token Expired.")
                os._exit(1) 
            
            elif status == "BLOCK":
                print(f"[{ts_end}]    [BLOCKED] Packet Rejected: {masked}")
                self.keep_data.append(item) 
                self.consecutive_errors += 1
            
            else: # NET_ERR
                self.keep_data.append(item) 
                self.consecutive_errors += 1

    def start_monitoring(self):
        print(f"[{get_ist()}]  [SYS_INIT] System Monitor v9.0 (Anti-Block Stealth Engine) Booting...")
        if not self.setup_session(): 
            print(f"[{get_ist()}]  [SYS_ERR] Connection failed.")
            return

        while True:
            # Lifecycle reset (every 6 hours)
            if time.time() - self.start_time > self.MAX_DURATION:
                print(f"\n[{get_ist()}]  [SYS_MAINTENANCE] Scheduled Restart Initiated.")
                break 

            # Fetch Batch
            current_data, filename = self.fetch_logs()
            
            if not current_data:
                print(f"[{get_ist()}]  [IDLE] No packets found. Standby 60s...")
                time.sleep(60)
                continue

            print(f"\n[{get_ist()}]  [SCAN] Analyzing {len(current_data)} data packets (Extreme Parallel Speed)...")
            
            self.keep_data = [] 
            self.corruption_detected = False 
            self.consecutive_errors = 0
            self.global_pause = False

            # --- SMART MULTI-THREADING ---
            # 15 workers provides exactly the 8-10 second clear time you requested without triggering the DDoS sensors.
            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                executor.map(self._worker, current_data)

            # Sync Updates
            if self.corruption_detected:
                print(f"\n[{get_ist()}]  [DB_SYNC] Removing invalid entries...")
                self.update_logs(self.keep_data, filename)
                print(f"[{get_ist()}]  [SYS] Data cleaned. Restarting check loop...")
                time.sleep(5) 
            else:
                # Slight wait between cycles ensures Akamai forgets our IP burst
                print(f"[{get_ist()}]  [SYS] System Stable. Waiting 3s for Next Cycle...")
                time.sleep(3)

if __name__ == "__main__":
    monitor = SystemHealthMonitor()
    monitor.start_monitoring()
