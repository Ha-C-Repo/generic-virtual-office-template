@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
color 0A

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║   YOUR COMPANY — CLAUDE API DIAGNOSTIC v3.1                ║
echo  ║   Run this FIRST to find exactly why Claude won't connect.  ║
echo  ║   Results saved to:  claude_diag.txt                        ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

set OUTFILE=claude_diag.txt
echo YOUR COMPANY — Claude API Diagnostic > %OUTFILE%
echo Run at: %DATE% %TIME% >> %OUTFILE%
echo. >> %OUTFILE%

REM ── Read API key from file ─────────────────────────────────────────────
set KEYFILE=API Keys\Claude API.txt
set CLAUDE_KEY=

if not exist "%KEYFILE%" (
    echo  [ERROR] API key file not found: %KEYFILE%
    echo  [ERROR] API key file not found: %KEYFILE% >> %OUTFILE%
    echo.
    echo  Make sure you run this from the virtualoffice\ folder.
    goto :end
)

set /p CLAUDE_KEY=<"%KEYFILE%"
set CLAUDE_KEY=%CLAUDE_KEY: =%
set CLAUDE_KEY=%CLAUDE_KEY:	=%

if "%CLAUDE_KEY%"=="" (
    echo  [FAIL] Claude API.txt is empty!
    echo  [FAIL] Claude API.txt is empty! >> %OUTFILE%
    goto :end
)

echo  Key loaded: %CLAUDE_KEY:~0,12%...%CLAUDE_KEY:~-4%
echo  Key length: 0
set LEN=0
set STR=%CLAUDE_KEY%
:strlen
if not "%STR%"=="" (
    set STR=%STR:~1%
    set /a LEN+=1
    goto :strlen
)
echo  Key loaded: %CLAUDE_KEY:~0,12%... >> %OUTFILE%
echo  Key length: %LEN% chars >> %OUTFILE%

if %LEN% LSS 40 (
    echo  [WARN] Key seems too short ^(%LEN% chars^). Valid keys are 90+ chars.
    echo  [WARN] Key seems too short >> %OUTFILE%
)

REM Check prefix
echo %CLAUDE_KEY% | findstr /C:"sk-ant-" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [WARN] Key does NOT start with 'sk-ant-'. Check for extra spaces or newlines in file.
    echo  [WARN] Key prefix wrong - does not start with sk-ant- >> %OUTFILE%
) else (
    echo  [OK]   Key starts with sk-ant- ^(correct prefix^)
    echo  [OK]   Key starts with sk-ant- >> %OUTFILE%
)

echo.
echo ──────────────────────────────────────────────────────────────
echo  TEST 1: DNS Resolution
echo ──────────────────────────────────────────────────────────────
echo TEST 1: DNS >> %OUTFILE%
nslookup api.anthropic.com 2>&1 | findstr /i "address name" >> %OUTFILE%
nslookup api.anthropic.com 2>&1 | findstr /i "address name"
if %errorlevel% equ 0 (
    echo  [OK]   DNS resolves api.anthropic.com
    echo  [OK]   DNS resolves >> %OUTFILE%
) else (
    echo  [FAIL] DNS cannot resolve api.anthropic.com
    echo  [FAIL] DNS cannot resolve -- check internet connection / firewall DNS block >> %OUTFILE%
)

echo.
echo ──────────────────────────────────────────────────────────────
echo  TEST 2: TCP Port 443 Connectivity
echo ──────────────────────────────────────────────────────────────
echo TEST 2: TCP 443 >> %OUTFILE%
powershell -Command "try { $r = Test-NetConnection api.anthropic.com -Port 443 -WarningAction SilentlyContinue; if ($r.TcpTestSucceeded) { Write-Host '  [OK]   TCP port 443 OPEN' } else { Write-Host '  [FAIL] TCP port 443 BLOCKED' } } catch { Write-Host '  [FAIL] Test-NetConnection failed' }" 2>&1
powershell -Command "try { $r = Test-NetConnection api.anthropic.com -Port 443 -WarningAction SilentlyContinue; if ($r.TcpTestSucceeded) { '[OK] TCP 443 open' } else { '[FAIL] TCP 443 blocked' } } catch { '[FAIL] Test-NetConnection failed' }" >> %OUTFILE% 2>&1

echo.
echo ──────────────────────────────────────────────────────────────
echo  TEST 3: SSL Certificate Issuer (who signed the cert?)
echo            Expected: Amazon / DigiCert
echo            Red flag: Zscaler / BitDefender / Netskope / Forcepoint
echo ──────────────────────────────────────────────────────────────
echo TEST 3: SSL issuer >> %OUTFILE%
curl.exe -svI https://api.anthropic.com/v1/messages 2>&1 | findstr /i "issuer subject certificate expire"
curl.exe -svI https://api.anthropic.com/v1/messages 2>&1 | findstr /i "issuer subject certificate expire" >> %OUTFILE%

echo.
echo ──────────────────────────────────────────────────────────────
echo  TEST 4: curl.exe — Windows Native HTTP (WinHTTP, not Python)
echo           This BYPASSES all Python SSL. If this works = Python SSL bug.
echo           If this fails = firewall or bad API key.
echo ──────────────────────────────────────────────────────────────
echo TEST 4: curl.exe WinHTTP >> %OUTFILE%

curl.exe -s -w "\nHTTP_STATUS:%%{http_code}\nTLS_ISSUER:%%{ssl_issuer}\n" ^
    -X POST "https://api.anthropic.com/v1/messages" ^
    -H "x-api-key: %CLAUDE_KEY%" ^
    -H "anthropic-version: 2023-06-01" ^
    -H "content-type: application/json" ^
    -d "{\"model\":\"claude-sonnet-4-20250514\",\"max_tokens\":5,\"messages\":[{\"role\":\"user\",\"content\":\"reply: pong\"}]}" ^
    -o curl_response.json ^
    2>&1

set CURL_EC=%errorlevel%

echo curl.exe exit code: %CURL_EC%
echo curl.exe exit code: %CURL_EC% >> %OUTFILE%

if exist curl_response.json (
    echo curl response body:
    type curl_response.json
    echo.
    echo curl response body: >> %OUTFILE%
    type curl_response.json >> %OUTFILE%
    echo. >> %OUTFILE%

    REM Check for success
    type curl_response.json | findstr /C:"\"type\":\"message\"" >nul 2>&1
    if !errorlevel! equ 0 (
        echo  ████████████████████████████████████████████████████████
        echo  █  [PASS] curl.exe CONNECTED TO CLAUDE SUCCESSFULLY!  █
        echo  █  Root cause: Python SSL/httpx issue ^(not firewall^).  █
        echo  █  Fix: replace bridge\api.py with curl-strategy build. █
        echo  ████████████████████████████████████████████████████████
        echo  [PASS] curl.exe succeeded - Python SSL bug confirmed >> %OUTFILE%
    )

    REM Check for auth error
    type curl_response.json | findstr /C:"authentication_error" >nul 2>&1
    if !errorlevel! equ 0 (
        echo  ████████████████████████████████████████████████████████
        echo  █  [KEY ERROR] API key is INVALID or EXPIRED!          █
        echo  █  Go to: console.anthropic.com/settings/keys          █
        echo  █  Create a new key, paste it into:                    █
        echo  █  API Keys\Claude API.txt  ^(no spaces, no quotes^)    █
        echo  ████████████████████████████████████████████████████████
        echo  [KEY ERROR] Authentication failed - key is invalid/expired >> %OUTFILE%
    )

    del curl_response.json >nul 2>&1
)

echo.
echo ──────────────────────────────────────────────────────────────
echo  TEST 5: Python urllib (Python's built-in, no httpx)
echo ──────────────────────────────────────────────────────────────
echo TEST 5: Python urllib >> %OUTFILE%

py -3 -c "
import urllib.request, json, sys

api_key = open('API Keys/Claude API.txt').read().strip()
payload = json.dumps({
    'model': 'claude-sonnet-4-20250514',
    'max_tokens': 5,
    'messages': [{'role': 'user', 'content': 'reply: pong'}]
}).encode()

req = urllib.request.Request(
    'https://api.anthropic.com/v1/messages',
    data=payload,
    headers={
        'Content-Type': 'application/json',
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
    },
    method='POST'
)

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
        print('[PASS] urllib connected! Response:', body.get('stop_reason', 'ok'))
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print('[HTTP ERROR]', e.code, body[:300])
except Exception as e:
    print('[FAIL]', type(e).__name__, str(e)[:300])
" 2>&1
py -3 -c "
import urllib.request, json, sys
api_key = open('API Keys/Claude API.txt').read().strip()
payload = json.dumps({'model':'claude-sonnet-4-20250514','max_tokens':5,'messages':[{'role':'user','content':'pong'}]}).encode()
req = urllib.request.Request('https://api.anthropic.com/v1/messages',data=payload,headers={'Content-Type':'application/json','x-api-key':api_key,'anthropic-version':'2023-06-01'},method='POST')
try:
    with urllib.request.urlopen(req, timeout=30) as r: print('[PASS] urllib ok:', json.loads(r.read()).get('stop_reason'))
except urllib.error.HTTPError as e: print('[HTTP ERROR]', e.code, e.read().decode()[:200])
except Exception as e: print('[FAIL]', type(e).__name__, str(e)[:200])
" >> %OUTFILE% 2>&1

echo.
echo ──────────────────────────────────────────────────────────────
echo  TEST 6: Python anthropic SDK + truststore (the current fix)
echo ──────────────────────────────────────────────────────────────
echo TEST 6: Python anthropic + truststore >> %OUTFILE%

py -3 -c "
import sys
api_key = open('API Keys/Claude API.txt').read().strip()
print('Key length:', len(api_key), '| Prefix OK:', api_key.startswith('sk-ant-'))

errors = {}

# Strategy 0: truststore
try:
    import ssl, truststore, anthropic
    from anthropic import DefaultHttpxClient
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    c = anthropic.Anthropic(api_key=api_key, http_client=DefaultHttpxClient(verify=ctx, http2=False, timeout=30))
    r = c.messages.create(model='claude-sonnet-4-20250514', max_tokens=5, messages=[{'role':'user','content':'pong'}])
    print('[PASS] truststore strategy worked!')
    sys.exit(0)
except Exception as e:
    errors['truststore'] = type(e).__name__ + ': ' + str(e)[:200]
    print('[FAIL] truststore:', errors['truststore'])

# Strategy 1: ssl.load_default_certs
try:
    import ssl, anthropic
    from anthropic import DefaultHttpxClient
    ctx = ssl.create_default_context()
    ctx.load_default_certs(ssl.Purpose.SERVER_AUTH)
    c = anthropic.Anthropic(api_key=api_key, http_client=DefaultHttpxClient(verify=ctx, http2=False, timeout=30))
    r = c.messages.create(model='claude-sonnet-4-20250514', max_tokens=5, messages=[{'role':'user','content':'pong'}])
    print('[PASS] ssl_default_certs strategy worked!')
    sys.exit(0)
except Exception as e:
    errors['ssl_default'] = type(e).__name__ + ': ' + str(e)[:200]
    print('[FAIL] ssl_default:', errors['ssl_default'])

# Strategy 2: default SDK
try:
    import anthropic
    c = anthropic.Anthropic(api_key=api_key)
    r = c.messages.create(model='claude-sonnet-4-20250514', max_tokens=5, messages=[{'role':'user','content':'pong'}])
    print('[PASS] default SDK worked!')
    sys.exit(0)
except Exception as e:
    errors['default_sdk'] = type(e).__name__ + ': ' + str(e)[:200]
    print('[FAIL] default_sdk:', errors['default_sdk'])

# Strategy 3: verify=False
try:
    import anthropic
    from anthropic import DefaultHttpxClient
    c = anthropic.Anthropic(api_key=api_key, http_client=DefaultHttpxClient(verify=False, http2=False, timeout=30))
    r = c.messages.create(model='claude-sonnet-4-20250514', max_tokens=5, messages=[{'role':'user','content':'pong'}])
    print('[PASS] verify=False worked! (TLS interception confirmed - corp proxy)')
    sys.exit(0)
except Exception as e:
    errors['verify_false'] = type(e).__name__ + ': ' + str(e)[:200]
    print('[FAIL] verify=False:', errors['verify_false'])

print()
print('ALL PYTHON STRATEGIES FAILED. Error summary:')
for k,v in errors.items():
    print(' ', k, '->', v)
" 2>&1
py -3 -c "
import sys
api_key = open('API Keys/Claude API.txt').read().strip()
errors = {}
try:
    import ssl, truststore, anthropic
    from anthropic import DefaultHttpxClient
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    c = anthropic.Anthropic(api_key=api_key, http_client=DefaultHttpxClient(verify=ctx, http2=False, timeout=30))
    c.messages.create(model='claude-sonnet-4-20250514', max_tokens=5, messages=[{'role':'user','content':'pong'}])
    print('[PASS] truststore'); sys.exit(0)
except Exception as e: errors['truststore'] = f'{type(e).__name__}: {e}'[:200]; print('[FAIL]', errors['truststore'])
try:
    import ssl, anthropic
    from anthropic import DefaultHttpxClient
    ctx = ssl.create_default_context(); ctx.load_default_certs(ssl.Purpose.SERVER_AUTH)
    c = anthropic.Anthropic(api_key=api_key, http_client=DefaultHttpxClient(verify=ctx, http2=False, timeout=30))
    c.messages.create(model='claude-sonnet-4-20250514', max_tokens=5, messages=[{'role':'user','content':'pong'}])
    print('[PASS] ssl_default'); sys.exit(0)
except Exception as e: errors['ssl_default'] = f'{type(e).__name__}: {e}'[:200]; print('[FAIL]', errors['ssl_default'])
try:
    import anthropic
    from anthropic import DefaultHttpxClient
    c = anthropic.Anthropic(api_key=api_key, http_client=DefaultHttpxClient(verify=False, http2=False, timeout=30))
    c.messages.create(model='claude-sonnet-4-20250514', max_tokens=5, messages=[{'role':'user','content':'pong'}])
    print('[PASS] verify=False'); sys.exit(0)
except Exception as e: errors['verify_false'] = f'{type(e).__name__}: {e}'[:200]; print('[FAIL]', errors['verify_false'])
for k,v in errors.items(): print(k, '->', v)
" >> %OUTFILE% 2>&1

:end
echo.
echo ══════════════════════════════════════════════════════════════
echo  Diagnostic complete. Full log saved to: claude_diag.txt
echo  Email claude_diag.txt to joseph@yourcompany.example.com if stuck.
echo ══════════════════════════════════════════════════════════════
echo.
pause
