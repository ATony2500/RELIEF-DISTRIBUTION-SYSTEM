"""Live page test — python test_pages.py"""
import urllib.request, urllib.parse, http.cookiejar

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", "NRDSTester/1.0")]

# Fetch login page to get CSRF token
login_page = opener.open("http://127.0.0.1:5000/login").read().decode()
import re
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page)
csrf = m.group(1) if m else ""
print(f"CSRF token: {csrf[:20]}...")

data = urllib.parse.urlencode({"username": "admin", "password": "Admin@1234", "csrf_token": csrf}).encode()
try:
    r = opener.open("http://127.0.0.1:5000/login", data)
    print(f"Login: {r.status}")
except Exception as e:
    print(f"Login FAILED: {e}"); raise SystemExit(1)

pages = [
    "/dashboard",
    "/beneficiaries/",
    "/beneficiaries/1",
    "/beneficiaries/register",
    "/inventory/warehouses",
    "/inventory/warehouses/1",
    "/inventory/items",
    "/inventory/items/1/move",
    "/distribution/",
    "/distribution/create",
    "/distribution/1",
    "/distribution/1/optimise-route",
    "/reports/",
    "/reports/beneficiary-summary",
    "/reports/beneficiary-summary/export",
    "/reports/inventory-report",
    "/reports/inventory-report/export",
    "/reports/distribution-report",
    "/reports/distribution-report/export",
    "/reports/audit-summary",
    "/admin/users",
    "/admin/users/create",
    "/admin/audit-log",
    "/admin/distribution-points",
    "/admin/distribution-points/create",
]

err_kw = [b"jinja2.", b"TemplateAssert", b"CompileError", b"OperationalError",
          b"AttributeError", b"Traceback", b"Internal Server Error", b"TypeError"]

ok = err = 0
for page in pages:
    try:
        r = opener.open("http://127.0.0.1:5000" + page)
        body = r.read(16384)
        found = [k.decode() for k in err_kw if k in body]
        if found:
            print(f"  ERR  {r.status}  {page}  {found}"); err += 1
        else:
            print(f"  OK   {r.status}  {page}"); ok += 1
    except urllib.error.HTTPError as e:
        body = e.read(4096)
        found = [k.decode() for k in err_kw if k in body]
        print(f"  HTTP {e.code}  {page}  {found or 'no detail'}"); err += 1
    except Exception as ex:
        print(f"  FAIL  {page}  {ex}"); err += 1

print(f"\n{'='*50}")
print(f"Results: {ok} OK  |  {err} errors")
