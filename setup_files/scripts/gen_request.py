
#!/usr/bin/env python3
import time
import jwt
import binascii
import json
import requests
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# === CONFIGURATION ===
JWT_SECRET_PATH = "chain_data/jwt-secret"
REQUEST_FILE = "rpc_request.json"
OUTPUT_FILE = "rpc_response_log.json"

# === READ TARGET CLIENTS FROM TERMINAL ===
if len(sys.argv) < 2:
    print("Usage: python3 gen_request.py <host1:port> <host2:port> ...")
    sys.exit(1)

TARGETS = [f"http://{target}" for target in sys.argv[1:]]

# === JWT GENERATION ===
def generate_jwt(secret_path):
    with open(secret_path, "r") as f:
        secret_hex = f.read().strip()
    secret_bytes = binascii.unhexlify(secret_hex)
    payload = {"iat": int(time.time())}
    token = jwt.encode(payload, secret_bytes, algorithm='HS256')
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

# === SEND REQUEST TO TARGET CLIENTS ===
def send_request_to_clients(request_data, jwt_token):
    responses = {}
    for url in TARGETS:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {jwt_token}"
        }
        try:
            response = requests.post(url, headers=headers, data=json.dumps(request_data))
            responses[url] = response.json()
        except Exception as e:
            responses[url] = {"error": str(e)}
    return responses

# === FILE MONITORING ===
class RequestFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(REQUEST_FILE):
            try:
                with open(REQUEST_FILE, 'r') as f:
                    request_data = json.load(f)
                jwt_token = generate_jwt(JWT_SECRET_PATH)
                responses = send_request_to_clients(request_data, jwt_token)

                print("\n=== Responses ===")
                for url, resp in responses.items():
                    print(f"\n-- {url} --")
                    print(json.dumps(resp, indent=2))

                with open(OUTPUT_FILE, 'a') as out_f:
                    log_entry = {
                        "timestamp": int(time.time()),
                        "request": request_data,
                        "responses": responses
                    }
                    out_f.write(json.dumps(log_entry, indent=2) + "\n\n")

            except Exception as e:
                print(f"Error processing request file: {e}")

# === MAIN ===
if __name__ == "__main__":
    print(f"Monitoring '{REQUEST_FILE}' for changes...")
    event_handler = RequestFileHandler()
    observer = Observer()
    observer.schedule(event_handler, ".", recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
