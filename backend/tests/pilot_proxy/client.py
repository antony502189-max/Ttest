"""Runs from two actual Docker source addresses through real Traefik/Nginx."""
import json
import sys
from uuid import uuid4

import httpx

phase = sys.argv[1]
client = httpx.Client(base_url="http://traefik:8080",headers={"Host":"app.112233.es"},trust_env=False,timeout=10)
basic = ("tester","fixture-password")  # Offline fixture credential, never a live password.
base = "/ai-pilot/api/v1/"
if phase == "a":
    assert client.get("/ai-pilot/").status_code == 401
    page = client.get("/ai-pilot/",auth=basic)
    assert page.status_code == 200 and "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert page.headers["permissions-policy"] == "camera=(), microphone=(self)"
    for path in ("auth/register","auth/login","payments","listings","admin","uploads","../docs","openapi.json","ai-search/unknown"):
        for method in ("GET","POST","PUT","DELETE"):
            response = client.request(method,base+path,auth=basic,json={"ignored":"never reach handler"})
            assert response.status_code in (403,404), (method,path,response.status_code)
            assert "set-cookie" not in response.headers
    for i in range(3):
        identity = client.post(base+"ai-search/identity",auth=basic,headers={"X-Real-IP":"172.30.41.11","X-Forwarded-For":"172.30.41.11"})
        assert identity.status_code == (200 if i<2 else 429), identity.text
        assert identity.json()["address"] == "172.30.41.10"
        if i<2:
            cookie = identity.headers["set-cookie"].lower()
            assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
            assert "path=/ai-pilot/api/v1/ai-search" in cookie
    direct = httpx.get("http://frontend:8443"+base+"private-demo/status",headers={"Host":"app.112233.es","X-Forwarded-For":"172.30.41.9","X-Real-IP":"172.30.41.9"},auth=basic,trust_env=False)
    assert direct.status_code == 403
    operation = {"idempotency_key":str(uuid4()),"text":"do not contact a provider"}
    first = client.post(base+"ai-search/query",auth=basic,json=operation).json()
    retry = client.post(base+"ai-search/query",auth=basic,json=operation).json()
    assert first == retry and first["mock_calls"] == 1
    operation["idempotency_key"] = str(uuid4())
    assert client.post(base+"ai-search/query",auth=basic,json=operation).json()["mock_calls"] == 2
else:
    response = client.post(base+"ai-search/identity",auth=basic)
    assert response.status_code == 200 and response.json()["address"] == "172.30.41.11"
status = client.get(base+"private-demo/status",auth=basic).json()
assert status["authorization_absent"] and status["forwarded_absent"] and status["unexpected_handlers"] == []
print(json.dumps({"phase":phase,"source_ip":status["address"],"checks":"PASS","external_provider_calls":0}))
