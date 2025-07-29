import time
import csv
import os
import requests
from datetime import datetime, timedelta
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
load_dotenv()
RATE_LIMIT = os.getenv("RATE_LIMIT", 100)
WINDOW_SECONDS = os.getenv("WINDOW_SECONDS", 3600)
REQUEST_LOGS_FILE =  "request_log.csv"

if not os.path.exists(REQUEST_LOGS_FILE):
    with open(REQUEST_LOGS_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "ip"])

class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "authkey" not in request.headers:
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"}
            )
        
        license_key = request.headers["authkey"]
        auth_payload = {
            "deviceMake": "Web",
            "deviceModel": "a10e",
            "osVersion": "9",
            "bundleId": "com.sample.test",
            "deviceUId": "testingscanflowa2",
            "platform" : "Android",
            "productType": ""
            }
        auth_url = "https://scanflowdev.azurewebsites.net/LicenseKey/ValidateLicenseKey"
        auth_headers = {
            "Content-Type": "application/json",
            "authkey": license_key
            }
        authresponse = requests.post(auth_url, headers=auth_headers, json=auth_payload)
        authresponse_json = authresponse.json()
        if authresponse.status_code == 200 and authresponse_json['status'] == "Success":
            response = await call_next(request)
            return response
        else:
            return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid license key"}
                )

def log_request(ip: str):
    with open(REQUEST_LOGS_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.utcnow().isoformat(), ip])


def count_recent_requests(ip: str) -> int:
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=int(WINDOW_SECONDS))
    count = 0

    with open(REQUEST_LOGS_FILE, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["ip"] == ip:
                timestamp = datetime.fromisoformat(row["timestamp"])
                if timestamp > cutoff:
                    count += 1
    return count


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host
        if count_recent_requests(ip) >= int(RATE_LIMIT):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."}
            )

        log_request(ip)

        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
