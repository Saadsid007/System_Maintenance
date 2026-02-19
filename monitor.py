import json
import time
import os
import requests # Used only for GitHub API (Gist Sync)
import sys
import logging
import base64
import random

# --- TURBO STEALTH ENGINE ---
try:
    from curl_cffi import requests as crequests
except ImportError:
    print(" [SYS_ERR] Critical Module 'curl_cffi' missing.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SYSTEM] %(message)s')
logger = logging.getLogger(__name__)

# Polymorphic Fingerprints (Rotating Identities)
FINGERPRINTS = [
    "chrome110", "chrome119", "chrome120", "chrome124",
    "edge99", "edge101", 
    "safari15_3", "safari17_0"
]

class SystemHealthMonitor:
    def __init__(self):
        self.config_str = os.environ.get('APP_CONFIG') 
        self.log_id = os.environ.get('LOG_ID')         
        self.api_key = os.environ.get('API_KEY')       
        
        self.cookie_string = ""
        self.start_time = time.time()
        self.MAX_DURATION = 21000 # ~6 hours safe limit

        if not self.log_id or not self.api_key:
            print(" [SYS_ERR] Config Missing (ID/KEY). Aborting.")
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
        return True

    # --- GITHUB GIST SYNC (Standard Requests) ---
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
            print(f" [CLOUD_ERR] Sync Failed: {e}")
            return [], ""

    def update_logs(self, valid_list, filename):
        headers = {"Authorization": f"token {self.api_key}"}
        new_content = "\n".join(valid_list)
        payload = {"files": {filename: {"content": new_content}}}
        try:
            requests.patch(f"https://api.github.com/gists/{self.log_id}", json=payload, headers=headers)
            print(" [CLOUD_SYNC] Database optimized & cleaned.")
        except: pass

    # --- TURBO CHECK ENGINE (curl_cffi) ---
    def ping_endpoint(self, code):
        url = self._d("aHR0cHM6Ly93d3cuc2hlaW5pbmRpYS5pbi9hcGkvY2FydC9hcHBseS12b3VjaGVy")
        payload = {"voucherId": code, "device": {"client_type": "web"}}
        
        # Identity Rotation
        fingerprint = random.choice(FINGERPRINTS)
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "origin": self._d("aHR0cHM6Ly93d3cuc2hlaW5pbmRpYS5pbg=="),
            "referer": self._d("aHR0cHM6Ly93d3cuc2hlaW5pbmRpYS5pbi9jYXJ0"),
            "x-tenant-id": self._d("U0hFSU4="), 
            "cookie": self.cookie_string
        }
        
        try:
            # Fast Request with browser impersonation
            resp = crequests.post(
                url, 
                json=payload, 
                headers=headers, 
                impersonate=fingerprint, 
                timeout=8
            )
            
            # 403 Protection
            if resp.status_code in [403, 429]:
                return {"status_code": resp.status_code}
                
            return resp.json()
        except Exception:
            return None

    def reset_endpoint(self, code):
        url = self._d("aHR0cHM6Ly93d3cuc2hlaW5pbmRpYS5pbi9hcGkvY2FydC9yZXNldC12b3VjaGVy")
        payload = {"voucherId": code, "device": {"client_type": "web"}}
        try:
            fingerprint = random.choice(FINGERPRINTS)
            crequests.post(
                url, json=payload, 
                headers={"cookie": self.cookie_string, "content-type": "application/json", "x-tenant-id": self._d("U0hFSU4=")}, 
                impersonate=fingerprint, timeout=3
            )
        except: pass

    def analyze_signal(self, data):
        if not data: return "NET_ERR"
        
        if "status_code" in data: return "BLOCK" # WAF blocked us
        
        if "errorMessage" in data:
            errors = data.get("errorMessage", {}).get("errors", [])
            for error in errors:
                msg = error.get("message", "").lower()
                if "cart" in msg and ("found" in msg or "empty" in msg): return "AUTH_FAIL"
                if "redeem" in msg or "limit" in msg or "used" in msg: return "ARCHIVED"
                if "not applicable" in msg or "not exist" in msg or "invalid" in msg: return "CORRUPT"
            return "CORRUPT"
        return "OK"

    def start_monitoring(self):
        print(" [SYS_INIT] Booting System Monitor v3.0 (Turbo)...")
        if not self.setup_session(): 
            print(" [SYS_ERR] Connection Handshake Failed.")
            return

        consecutive_errors = 0

        while True:
            # Lifecycle Management
            if time.time() - self.start_time > self.MAX_DURATION:
                print("\n [SYS_MAINTENANCE] Scheduled Restart.")
                break 

            # Fetch Batch
            current_data, filename = self.fetch_logs()
            
            if not current_data:
                print(" [IDLE] No packets found. Standby 60s...")
                time.sleep(60)
                continue

            print(f"\n [SCAN] Analyzing {len(current_data)} data packets (Speed: High)...")
            
            keep_data = [] 
            corruption_detected = False 

            for item in current_data:
                # 403 Safety Cutoff
                if consecutive_errors > 5:
                    print(" [WARN] Network Congestion. Cooling down 10s...")
                    time.sleep(10)
                    consecutive_errors = 0

                masked = item[:3] + "*****" 
                
                # Turbo Delay (0.1s - 0.4s)
                time.sleep(random.uniform(0.1, 0.4))

                resp = self.ping_endpoint(item)
                status = self.analyze_signal(resp)
                
                if status == "OK":
                    print(f"   [OK] Verified: {masked}")
                    self.reset_endpoint(item)
                    keep_data.append(item)
                    consecutive_errors = 0
                
                elif status == "ARCHIVED":
                    print(f"   [WARN] Archived: {masked}")
                    self.reset_endpoint(item)
                    keep_data.append(item)
                    consecutive_errors = 0
                
                elif status == "CORRUPT":
                    print(f"   [ERR] Corrupt Data: {masked} -> Purging")
                    # corruption_detected = True
                    consecutive_errors = 0
                
                elif status == "AUTH_FAIL":
                    print(" [CRITICAL] Session Token Expired.")
                    sys.exit(1)
                
                elif status == "BLOCK":
                    print(f"   [BLOCKED] Packet Rejected: {masked}")
                    keep_data.append(item)
                    consecutive_errors += 1
                
                else: # NET_ERR
                    keep_data.append(item)
                    consecutive_errors += 1

            # Sync Updates
            if corruption_detected:
                print("\n [DB_SYNC] Removing invalid entries...")
                self.update_logs(keep_data, filename)
                print(" [SYS] Optimization Complete. Restarting Scan...")
                # Short delay to prevent Gist spamming
                time.sleep(5) 
            else:
                print(" [SYS] System Stable. Next Cycle...")
                time.sleep(1)

if __name__ == "__main__":
    monitor = SystemHealthMonitor()
    monitor.start_monitoring()
