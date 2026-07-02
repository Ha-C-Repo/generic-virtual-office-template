"""
Your Company Virtual Office - Claude App Integration

Generates the configuration for the Owner's Windows Claude desktop app
to connect to the Virtual Office MCP server.

After setup, Owner can:
  "What's my bid pipeline?"      → Claude calls get_pipeline via MCP
  "How's compliance?"            → Claude calls get_ravs_scorecard
  "Run a bid on this email"      → Claude calls compose_full_bid
  "Log 50 tons fab today ICD"    → Claude calls log_production
  "Show me everything about AFR" → Claude calls knowledge_query

The Claude app becomes the natural-language front door to the
entire 215-method, 70-module Virtual Office.
"""

import json, os


def generate_claude_config(install_path: str = r"C:\YourCompany\virtualoffice") -> dict:
    """Generate the claude_desktop_config.json content for the Owner's Claude app.

    File location: %APPDATA%\\Claude\\claude_desktop_config.json
    (typically C:\\Users\\Owner\\AppData\\Roaming\\Claude\\claude_desktop_config.json)
    """
    config = {
        "mcpServers": {
            "your-company-office": {
                "command": "python",
                "args": [f"{install_path}\\mcp_server.py"],
                "env": {
                    "PYTHONPATH": install_path,
                },
            }
        }
    }

    return {
        "config": config,
        "config_json": json.dumps(config, indent=2),
        "file_path": r"%APPDATA%\Claude\claude_desktop_config.json",
        "instructions": get_setup_instructions(install_path),
    }


def get_setup_instructions(install_path: str = r"C:\YourCompany\virtualoffice") -> list:
    """Step-by-step setup instructions for Owner."""
    return [
        "═══ YOUR COMPANY VIRTUAL OFFICE - CLAUDE APP SETUP ═══",
        "",
        "Step 1: Install the Virtual Office",
        f"  • Extract YourCo_VirtualOffice_EXE.zip to {install_path}",
        f"  • Verify: {install_path}\\mcp_server.py exists",
        "",
        "Step 2: Install Python dependencies (one-time)",
        f'  • Open Command Prompt as Administrator',
        f'  • cd {install_path}',
        f'  • pip install -r requirements.txt',
        "",
        "Step 3: Configure Claude Desktop App",
        f'  • Open File Explorer',
        f'  • Navigate to: %APPDATA%\\Claude\\',
        f'  • Open (or create) claude_desktop_config.json',
        f'  • Paste the following:',
        "",
        json.dumps({
            "mcpServers": {
                "your-company-office": {
                    "command": "python",
                    "args": [f"{install_path}\\mcp_server.py"],
                }
            }
        }, indent=2),
        "",
        f'  • Save the file',
        f'  • Restart the Claude desktop app',
        "",
        "Step 4: Verify Connection",
        '  • Open Claude app',
        '  • You should see a 🔌 icon indicating MCP tools are available',
        '  • Say: "What tools do you have from Your Company?"',
        '  • Claude should list 19 Virtual Office tools',
        "",
        "Step 5: Test It",
        '  • Say: "Give me my morning brief"',
        '  • Say: "How\'s our compliance?"',
        '  • Say: "Estimate 500 tons of structural steel"',
        '  • Say: "Show me everything about ICD"',
        "",
        "═══ WHAT OWNER CAN NOW SAY TO CLAUDE ═══",
        "",
        "DAILY:",
        '  "Morning brief"',
        '  "What\'s on my plate today?"',
        '  "Any certs expiring soon?"',
        "",
        "BIDS:",
        '  "Run this bid through the system: [paste email]"',
        '  "What\'s our bid pipeline?"',
        '  "Estimate 300 tons, church project in Katy"',
        "",
        "SHOP:",
        '  "Log 47 tons erected today on ICD, 6-man crew"',
        '  "Show me the production board"',
        '  "What\'s our tons-per-day this week?"',
        "",
        "FINANCIALS:",
        '  "Cash flow projection - we have $180K in the bank"',
        '  "AR aging report"',
        '  "How\'s the ICD project P&L?"',
        "",
        "INTELLIGENCE:",
        '  "Latest steel prices"',
        '  "Best price on W sections right now"',
        '  "What Houston projects should we be chasing?"',
        '  "Show me everything about Marathon"',
        "",
        "SYSTEM:",
        '  "Run the system self-test"',
        '  "Agent health check"',
        '  "How much are we saving vs paid APIs?"',
    ]


def get_available_tools() -> list:
    """List all tools available through the MCP server."""
    return [
        {"tool": "get_morning_brief", "voice": "Morning brief / What's on my plate today?"},
        {"tool": "get_agent_health", "voice": "Agent health check / How's the system?"},
        {"tool": "run_self_test", "voice": "Run the self-test"},
        {"tool": "get_pipeline", "voice": "Bid pipeline / What bids are we working?"},
        {"tool": "compose_full_bid", "voice": "Run this bid through the system"},
        {"tool": "run_compliance_check", "voice": "Compliance pre-flight for [project]"},
        {"tool": "get_latest_steel_prices", "voice": "Steel prices / What's HRC at?"},
        {"tool": "get_best_steel_price", "voice": "Best price on W sections"},
        {"tool": "get_project_pipeline", "voice": "Houston pipeline / What projects to chase?"},
        {"tool": "get_ravs_scorecard", "voice": "Compliance scorecard / ISN grade"},
        {"tool": "check_expiring_certs", "voice": "Certs expiring soon?"},
        {"tool": "get_calibrated_estimate", "voice": "Estimate [X] tons"},
        {"tool": "get_production_board", "voice": "Production board / Where's every piece?"},
        {"tool": "log_production", "voice": "Log 47 tons erected today ICD"},
        {"tool": "get_cash_flow_projection", "voice": "Cash flow / When do we go negative?"},
        {"tool": "knowledge_query", "voice": "Show me everything about [X]"},
        {"tool": "get_financial_dashboard", "voice": "Financial dashboard"},
        {"tool": "get_ar_aging", "voice": "AR aging / Who owes us?"},
    ]


def get_dual_account_strategy() -> dict:
    """Explain the dual-account token strategy."""
    return {
        "strategy": "Two Claude subscriptions, optimally split",
        "joseph_api": {
            "account": "Joseph's Anthropic API",
            "billing": "Pay-per-token",
            "best_for": "Background agents (daily 4AM pipeline), batch processing (takeoff, spec parsing), document generation (proposals, G702s)",
            "runs": "Automated - no human interaction needed",
        },
        "owner_app": {
            "account": "the Owner's Claude Desktop App",
            "billing": "Flat monthly subscription",
            "best_for": "Conversational queries (briefs, lookups, estimates), real-time decisions (bid go/no-go), voice-first field commands",
            "runs": "On-demand - Owner asks, Claude answers via MCP",
        },
        "why_this_works": [
            "the Owner's subscription is flat-rate - unlimited conversational queries at no marginal cost",
            "Joseph's API is pay-per-token - efficient for batch work that runs once/day",
            "Heavy processing (takeoff, document parsing) uses API tokens wisely",
            "Light queries (morning brief, price lookup) use the Owner's unlimited plan",
            "Neither account is wasted - each does what it's best at",
        ],
    }
