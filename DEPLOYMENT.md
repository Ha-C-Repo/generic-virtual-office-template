# Your Company Virtual Office - Deployment Guide

## Quick Update (v3.0.5)

### Replace one file:
```
1. Download YourCo_VirtualOffice_EXE.zip
2. Extract bridge/api.py from the ZIP
3. Copy to: C:\Users\josep\Documents\YourCoVirtualOffice-v3.0.4\YourCoVirtualOffice\bridge\api.py
4. Re-run the EXE
5. Type "test connection" in chat
```

### What this fixes:
- Claude connection: urllib fallback bypasses httpx HTTP/2 issue
- Error messages: Clean, actionable messages instead of raw dumps

---

## API Key Setup

### Claude (Anthropic) - console.anthropic.com
1. Sign up / log in at console.anthropic.com
2. Settings → API Keys → Create Key
3. Copy the key (starts with `sk-ant-`)
4. Save to: `API Keys/Claude API.txt` (just the key, nothing else)
5. Add $5-10 credit at Settings → Billing

### Gemini (Google) - aistudio.google.com
1. Go to aistudio.google.com/apikey
2. Create API Key
3. Save to: `API Keys/Gemini API.txt`
4. **IMPORTANT**: Free tier = 20 requests/day
5. To upgrade: console.cloud.google.com/billing → add payment method

### OpenAI - platform.openai.com
1. Sign up / log in at platform.openai.com
2. API Keys → Create new secret key
3. Copy the key (starts with `sk-`)
4. Save to: `API Keys/OpenAI API.txt`
5. Add credits: Settings → Billing → Add payment method → $10 minimum

---

## What Owner Can Say

### Daily Operations
| Say this | What happens |
|----------|-------------|
| "Morning brief" | Steel prices + pipeline + compliance + blockers |
| "What's on my plate?" | Same as morning brief |
| "Any certs expiring?" | Checks certificates within 30 days |

### Bidding
| Say this | What happens |
|----------|-------------|
| "Run this bid: [paste email]" | Full 12-step autonomous bid chain |
| "What's our pipeline?" | All bids with status |
| "Estimate 300 tons, church in Katy" | Calibrated estimate with GP% |
| "Win probability on Baytown?" | Historical pattern match + AISC baseline |

### Steel Intelligence
| Say this | What happens |
|----------|-------------|
| "Steel prices" | FRED PPI + CME HRC + AISI utilization |
| "Steel market brief" | Full Steel Price Agent analysis |
| "Best price on W sections" | Cheapest across service-center quotes |

### Shop Floor
| Say this | What happens |
|----------|-------------|
| "Log 47 tons erected today ICD, 6-man crew" | Writes to production tracker |
| "Production board" | Station-by-station status |

### Financial
| Say this | What happens |
|----------|-------------|
| "Cash flow - $180K in the bank" | 30/60/90 day projection |
| "Who owes us?" | AR aging report |

### System
| Say this | What happens |
|----------|-------------|
| "Test connection" | Check all 3 AI providers |
| "Run self-test" | 47 tests across every module |
| Ctrl+K | Command palette (15 quick actions) |
| Key 1-4 | Switch tabs (Status/Chat/Field/Settings) |

---

## Provider Status & Routing

| Provider | Route | Cost | Best For |
|----------|-------|------|----------|
| Claude | Rules/voice/strategic | $3/M tokens | Complex reasoning, proposals |
| GPT-4o | Math/structured data | $2.50/M tokens | Estimates, calculations |
| Gemini | Vision/market/PDF | Free (20/day) or $0.075/M | PDF analysis, web search |

Tasks auto-route to the best provider. If one fails, the system falls back to the next.

---

## Troubleshooting

### Claude says "Connection error"
→ v3.0.5 adds urllib fallback. Replace bridge/api.py and restart.
→ If still failing: `py -3.13 -m pip install --upgrade anthropic httpx h2`

### Gemini says "quota exceeded"
→ Free tier = 20 requests/day. Wait until midnight Pacific or upgrade billing.

### OpenAI says "429"
→ Add credits at platform.openai.com/account/billing ($10 minimum)

### App won't start
→ Check: `py -3.13 -m pip install pywebview google-generativeai anthropic openai`
→ Run from command line to see errors: `cd YourCoVirtualOffice && py -3.13 main.py`
