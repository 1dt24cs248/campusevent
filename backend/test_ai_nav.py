import httpx
import sys

BASE = "http://localhost:8005"
c = httpx.Client(base_url=BASE, timeout=30.0)

def login(email="management@demo.local", password="Demo@1234"):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} -- {detail}")

print("\n=== AI & Navigation Tests ===")
token = login()
headers = {"Authorization": f"Bearer {token}"}

# AI Tests
r = c.post("/api/ai/chat", json={"message": "Where is my next class?"}, headers=headers)
test("AI endpoint works", r.status_code == 200, r.text)

r = c.post("/api/ai/chat", json={"message": "Why did my room change?"}, headers=headers)
test("AI room change query works", r.status_code == 200, r.text)

r = c.post("/api/ai/chat", json={"message": "Hello!"}, headers=headers)
test("AI fallback works", r.status_code == 200 and "sorry" in r.json()["response"].lower(), r.text)

# Nav Tests
# We need a real room_id for this. Using room_A101 as it's standard.
r = c.get("/api/nav/route?target=room_A101", headers=headers)
test("Nav route works for valid room", r.status_code == 200, r.text)

r = c.get("/api/nav/route?target=room_INVALID", headers=headers)
test("Nav route returns 404 for invalid room", r.status_code == 404, r.text)

print(f"\nRESULTS: {passed}/{passed+failed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
