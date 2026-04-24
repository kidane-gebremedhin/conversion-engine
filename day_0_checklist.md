# Day 0 — Pre-flight Checklist

Complete before Day 1. Roughly four hours. A readiness review on Day 1 morning confirms each item.

| Item | What done looks like |
| :--- | :--- |
| **Resend or MailerSend account provisioned** | Free-tier account live. Sent one test email to your own address and received it. Webhook URL registered for reply handling. |
| **Africa's Talking sandbox** | Account created. Virtual short code registered. One test SMS routed to your webhook handler. |
| **HubSpot Developer Sandbox** | App created. MCP server installed. One test contact created via API. |
| **Cal.com running locally** | `docker compose up` succeeds. One test booking flows end-to-end. |
| **Langfuse cloud** | Project created. One test trace visible. |
| **τ²-Bench cloned** | Retail domain runs against pinned dev-tier model on three tasks. |
| **Seed repo forked** | Tenacious ICP, sales deck, email sequences, pricing sheet, bench summary all present. `style_guide.md` reviewed. |
| **Signal pipeline skeleton** | Playwright installs. A 10-line script fetches one public job listing and saves it as JSON. |
| **Data-handling policy signed** | Signed digital acknowledgement filed with program staff. |

---

## Technical Guidelines & Clarifications

### 1. Webhook URL Project Structure
You do **not** need a separate FastAPI project for webhooks. It is recommended to place the webhook endpoints inside your main backend project. 
- You can route different webhooks (like email replies vs. SMS events vs. Playwright signal scrapers) to different API paths (e.g., `/webhooks/email`, `/webhooks/sms`) all running on the same centralized backend.

### 2. HubSpot MCP Server
"MCP server installed" refers to the Model Context Protocol. You don't need to manually configure low-level API queries to HubSpot if you install a HubSpot MCP server. This gives your LLM agent native access to read/write records (like inserting the test contact) directly via standard tool calls rather than creating all custom API logic.

### 3. Playwright Installs
Playwright is an automation/web-scraping library. "Playwright installs" simply means successfully running `pip install playwright` (and potentially `playwright install` for the browser binaries) in your environment to prove the pipeline can run headless browsers to scrape public job listings into a JSON file. 

### 4. τ²-Bench Setup
"τ²-Bench cloned & Retail domain runs against pinned dev-tier model on three tasks":

To run the **actual** live implementation:
1. **Clone the real repository** side-by-side (ideally outside your main working directory so it isn't tracked in your git history): 
   `git clone https://github.com/sierra-research/tau2-bench`
2. **Install it** into your python environment globally: 
   `pip install -e /path/to/tau2-bench`
3. **Modify the harness:** Open `eval/harness.py` inside your project and replace the mocked logic inside the `_run_task` method. Import `tau2_bench` and feed the benchmark's simulated conversation turns directly to your LLM agent.
4. **Run the integration:** To test only three tasks quickly, open `eval/dev_slice.json` and keep only the first 3 items in the `"tasks"` array. Then run `make baseline` in your project root to initiate the real benchmark loop!
