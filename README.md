# agentic-threat-emulation

An agent that checks whether a detection rule actually catches the technique it
claims to cover. It reads a rule, runs the matching atomic on an isolated lab
VM, and reads the telemetry back from Microsoft Sentinel to decide one of three
verdicts: detected, gap, or blind.

This is the lab behind the Underground Labs #02 post.

## The idea

A detection rule declares a technique in its MITRE mapping. That mapping is a
claim, not proof. The only way to know if it holds is to run the technique and
look at what the detection saw. When you look, there are three outcomes:

- **detected**: telemetry arrived and the rule fired.
- **gap**: telemetry arrived, the rule did not fire. A weak rule.
- **blind**: no telemetry at all. Missing collection, where no rule could fire.

"gap" and "blind" look identical on a dashboard (no alert) but are opposite
problems. Separating them is the point of the lab.

## How it works

```
read rule  ->  pick atomic  ->  execute (MCP)  ->  check telemetry  ->  verdict
 (DaC repo)      (LLM)          (on the VM)        (Sentinel)       detected/gap/blind
```

The model only picks the atomic. Everything that decides the verdict is
deterministic code, so the verdict cannot be faked by the model deciding it is
done.

## Components

- `Agent/` — the agent
  - `Tools/read_rule.py` — reads a rule from the DaC repo, extracts technique and query
  - `Tools/check_telemetry.py` — the three-way verdict against Sentinel
  - `Clients/sentinel.py` — runs KQL against the workspace
  - `Clients/mcp.py` — connects to the Atomic Red Team MCP server
  - `run_loop.py` — the full loop end to end
- `Infra/` — Terraform for the lab VM, Sysmon, AMA, and the Sentinel DCR
- `Scripts/` — `install-lab.ps1` (provisioning), `start-lab.ps1` (start the lab)

## Stack

LangChain, the Atomic Red Team MCP server (by CyberBuff), Microsoft Sentinel,
an isolated Windows VM on Azure, and OpenAI gpt-4o-mini to pick the atomic.

## Running the lab

The lab has two sides: the VM that runs the atomics and ships telemetry to
Sentinel, and the agent that reads a rule, drives the emulation, and checks the
verdict. Terraform builds the VM and the telemetry pipeline. The lab tools and
the MCP are set up on the VM by the analyst, so the offensive execution endpoint
only exists while someone is using it.

### 1. Build the VM (Terraform)

From `Infra/`:

```bash
terraform init
terraform apply -var-file=secrets.tfvars
```

This provisions the Windows VM, the network (RDP locked to your IP), the AMA, and
the DCR that collects the Sysmon channel into the `log-analyst-de-lab` workspace.
It also runs `provision.ps1` on the VM (via an Azure Run Command), which installs
Sysmon, uv, git, Atomic Red Team and ngrok, sets Defender exclusions for the
atomics, and drops `start-lab.ps1` at `C:\lab\`. Status is logged to
`C:\lab-install.log`. After this, telemetry from the VM reaches Sentinel.

### 2. Start the lab (on the VM)

RDP into the VM, then:

```powershell
cd C:\lab
.\start-lab.ps1
```

The first run asks for your ngrok authtoken (from dashboard.ngrok.com), saves it
to the ngrok config on the VM, and then starts. Later runs skip the prompt. The
token never leaves the VM; it is not in git or Terraform.

It starts the MCP server (execution and auth enabled) and an ngrok tunnel, each
in its own window, and prints two things:

- the MCP auth token
- the public ngrok URL

Keep both windows open; closing them stops the lab.

### 3. Point the agent at the lab

In the agent's `.env` (gitignored):

```
OPENAI_API_KEY=sk-...
SENTINEL_WORKSPACE_ID=<workspace customer id>
MCP_URL=https://<ngrok-id>.ngrok-free.app/mcp
MCP_AUTH_TOKEN=<the token start-lab printed>
```

`MCP_URL` and `MCP_AUTH_TOKEN` come from `start-lab.ps1`. The ngrok URL changes
every time the tunnel restarts, so update `MCP_URL` each session.

### 4. Run

```bash
az login
cd Agent
python run_loop.py
```

The agent reads the rule, picks an atomic for its technique, executes it on the
VM through the MCP, waits for telemetry, and prints the verdict.

### Cost

The VM is the only thing that costs while running. Deallocate it between
sessions:

```bash
az vm deallocate -g ai-purple-rg -n ai-purple-vm
```

## Safety

The atomics do real, sometimes destructive things. They run only on the
isolated lab VM, which is disposable: Terraform rebuilds it from scratch. The
MCP execution endpoint is off by default and reached only over an authenticated
tunnel. The agent selects from reviewed atomics; it does not generate offensive
code.