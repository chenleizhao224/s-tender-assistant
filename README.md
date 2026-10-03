# Schick Tender Assistant

Draft Tender Brief + Python-calculated indicative value + assumptions and risks,
for an estimator to review. Final target: Microsoft Foundry, then internal Teams access.
The hosted `main.py` is still the original sample entry point; the demo pipeline is
not yet wired into that hosted endpoint.

## Code layout and local development

The service stays at `src/agent-framework-agent-basic-responses` so the existing
Foundry and Docker configuration remains valid. Its code is now organized into:

```text
src/agent-framework-agent-basic-responses/
├── main.py                     # Existing Foundry entry point
├── tender_assistant/
│   ├── pricing/                # Decimal calculation, rates, matching validation, snapshots
│   ├── text/                   # Document text extraction and Luna summaries
│   ├── schedules/              # Excel schedule extraction, classification, quantities
│   ├── documents/              # Document inventory and file fingerprints
│   ├── reporting/              # Combined HTML report and standalone brief
│   ├── cli/                    # Matching/batch commands and inspection utilities
│   └── paths.py                # Stable service root for .env and saved outputs
├── tests/                      # Unit and command-line regression tests
├── pyproject.toml
├── uv.lock
└── Dockerfile
```

Run commands from the service folder with its virtual environment active:

```sh
cd src/agent-framework-agent-basic-responses
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m tender_assistant.cli.match_rates --help
python -m tender_assistant.cli.match_rates --replay outputs/matches/row-105-v1.json
python -m tender_assistant.reporting.demo outputs/batches/BATCH_FILE.json --summary outputs/summaries/estimator-brief-v1.json --output outputs/reports/demo-new.html
```

Replace `BATCH_FILE.json` with an existing saved batch. Rendering and replay are
offline. Existing snapshots and output paths remain valid; existing output files
are never overwritten. No dependencies or model prompts changed in this reorganization.

### Old command → new command

| Previous script | New module command (`python -m ...`) |
| --- | --- |
| `try_rate_matching.py` | `tender_assistant.cli.match_rates` |
| `batch_rate_matching.py` | `tender_assistant.cli.batch_rates` |
| `tender_text.py` | `tender_assistant.text.extraction` |
| `tender_summary.py` | `tender_assistant.text.summary` |
| `demo_report.py` | `tender_assistant.reporting.demo` |
| `estimator_brief.py` | `tender_assistant.reporting.estimator_brief` |
| `document_inventory.py` | `tender_assistant.documents.inventory` |
| `inspect_schedules.py` | `tender_assistant.cli.inspect_schedules` |
| `compare_schedules.py` | `tender_assistant.cli.compare_schedules` |

Use modules, not `python tender_assistant/.../file.py`. For a single test module,
use `python -m unittest tests.test_pricing_engine -v`. Direct Python imports now
use package paths, e.g. `from tender_assistant.pricing.engine import calculate_item_value`.
The two schedule inspection utilities still use the original local sample paths.

Keep `.env`, tender inputs, historical rate files and generated `outputs/` local
and out of Git. The section below is retained starter documentation, not an
instruction to reinitialize or provision this existing project.

## Original hosted-agent starter reference

A minimal [Agent Framework](https://github.com/microsoft/agent-framework) agent hosted on Microsoft Foundry using the **Responses protocol**. This sample demonstrates basic request/response interaction and multi-turn conversations.

## How it works

The agent uses `FoundryChatClient` from the Agent Framework and is served via `ResponsesHostServer`, which exposes a REST API compatible with the OpenAI Responses protocol. See [main.py](src/agent-framework-agent-basic-responses/main.py) for the implementation.

## Option 1: Azure Developer CLI (`azd`)

<details>
<summary><strong>Show steps</strong></summary>

### Prerequisites

1. **Azure Developer CLI (`azd`)** — [Install azd](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd)
2. Install the AI agent extension:
   ```bash
   azd ext install microsoft.foundry
   ```
3. Authenticate:
   ```bash
   azd auth login
   ```

### Initialize the agent project

No cloning required. Create a new folder and initialize from the manifest:

```bash
mkdir my-basic-agent && cd my-basic-agent

azd ai agent init -m https://github.com/microsoft-foundry/foundry-samples/blob/main/samples/python/hosted-agents/agent-framework/responses/01-basic/azure.yaml
```

Follow the prompts to configure your Foundry project and model deployment. If you don't have an existing Foundry project, `azd ai agent init` will guide you through creating one.

### Provision Azure resources (if needed)

If you don't already have a Foundry project and model deployment:

```bash
azd provision
```

### Run the agent locally

```bash
azd ai agent run
```

The agent host will start on `http://localhost:8088`.

### Invoke the local agent

In a separate terminal, from the project directory:

```bash
azd ai agent invoke --local "Hi"
```

### Deploy to Foundry

Once tested locally, deploy to Microsoft Foundry:

```bash
azd deploy
```

For the full deployment guide, see [Deploy a hosted agent](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent).

### Invoke the deployed agent

```bash
azd ai agent invoke "Hi"
```

</details>

## Option 2: VS Code (Foundry Toolkit)

### Prerequisites

1. **VS Code** with the **[Foundry Toolkit](https://marketplace.visualstudio.com/items?itemName=ms-windows-ai-studio.windows-ai-studio)** extension installed.
2. For debugging Python in VS Code, install the **[Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)** extension pack.

### Set up the Python virtual environment

- With Python 3.13 or later and [pipx](https://pipx.pypa.io/stable/installation/), install uv outside the project environment, then let uv create and synchronize the locked environment:

  ```bash
   pipx install uv==0.11.7
   uv sync --frozen --python 3.13
  ```
- Open the Command Palette (`Ctrl+Shift+P`), run **Python: Select Interpreter**, and select the `.venv` created by uv.

### Run and debug the agent

Press **F5** to start the agent. The agent starts and the **Agent Inspector** opens automatically. Chat with the agent in the Inspector.

### Or run manually, then open the Inspector

1. Set the required environment variables and sign in to Azure with the Azure CLI (`az login`).
2. Start the agent: `uv run --no-sync python main.py` (listens on `http://localhost:8088`).
3. Command Palette (`Ctrl+Shift+P`) → **Foundry Toolkit: Open Agent Inspector**, then send a message to test.

### Deploy to Foundry

1. Open the Command Palette (`Ctrl+Shift+P`) and run **Foundry Toolkit: Deploy Hosted Agent**. The extension opens a **Deploy Hosted Agent** wizard and reads `agent.yaml` to auto-populate settings.
2. If prompted, complete **Foundry Project Setup** to select subscription and project.
3. On the **Basics** tab, choose deployment method (**Code** or **Container**) and confirm the agent name.
4. On **Review + Deploy**, confirm runtime details, pick **CPU and Memory** size, and click **Deploy**.
5. After deployment, invoke the agent in the Agent Playground and stream live logs from the **Logs** tab.

## Next steps

- [Quickstart: Create a hosted agent](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent) — end-to-end walkthrough using `azd`
- [Tool catalog](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/tool-catalog) — browse available tools to extend your agent (Bing Search, Azure AI Search, file search, code interpreter, and more)
- [Manage hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/manage-hosted-agent) — monitor and manage deployed agents
- [Add tools to your agent](https://github.com/microsoft-foundry/foundry-samples/tree/be4706c76acfe44e2ae99c2818efdc4c5ab25bd9/samples/python/hosted-agents/agent-framework/responses/02-tools/) — sample with local tool functions
- [Use Foundry Toolbox](https://github.com/microsoft-foundry/foundry-samples/tree/be4706c76acfe44e2ae99c2818efdc4c5ab25bd9/samples/python/hosted-agents/agent-framework/responses/04-foundry-toolbox/) — sample with Azure Foundry Toolbox integration
