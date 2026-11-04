# provision.ps1
# One provisioning script, run once by the Custom Script Extension when the VM
# comes up. Installs Sysmon, sets Defender exclusions, installs uv, git, Atomic
# Red Team and ngrok, and drops start-lab.ps1 on disk. Each step is isolated,
# so one failure does not stop the rest. Status: C:\lab-install.log.
#
# It installs the tools. It does NOT start the MCP or ngrok; the analyst runs
# start-lab.ps1 for that.

Start-Transcript -Path "C:\lab-provision-transcript.log" -Append -Force | Out-Null
$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"

New-Item -ItemType Directory -Force -Path "C:\lab" | Out-Null
function Log($m) { "$(Get-Date -Format o)  $m" | Tee-Object -FilePath C:\lab-install.log -Append }
Log "provision started"

# --- Sysmon ---------------------------------------------------------------
try {
    $sysDir = "C:\lab\sysmon"
    New-Item -ItemType Directory -Force -Path $sysDir | Out-Null
    Invoke-WebRequest "https://download.sysinternals.com/files/Sysmon.zip" -OutFile "$sysDir\Sysmon.zip" -UseBasicParsing
    Expand-Archive "$sysDir\Sysmon.zip" -DestinationPath $sysDir -Force
    Invoke-WebRequest "https://raw.githubusercontent.com/SwiftOnSecurity/sysmon-config/master/sysmonconfig-export.xml" -OutFile "$sysDir\config.xml" -UseBasicParsing
    & "$sysDir\Sysmon64.exe" -accepteula -i "$sysDir\config.xml"
    Log "Sysmon installed"
} catch { Log "Sysmon failed: $($_.Exception.Message)" }

# --- Defender exclusions --------------------------------------------------
# Real-time protection cannot be turned off reliably by script (Tamper
# Protection reverts it), so we exclude the atomics instead. Telemetry comes
# from Sysmon, not Defender, so this does not affect collection; it only stops
# Defender from killing tests mid-run.
foreach ($p in @("C:\AtomicRedTeam", "C:\lab", "C:\tools\uv", "C:\ngrok")) {
    try { Add-MpPreference -ExclusionPath $p -ErrorAction Stop; Log "excluded $p" } catch {}
}
foreach ($proc in @("powershell.exe", "pwsh.exe", "cmd.exe")) {
    try { Add-MpPreference -ExclusionProcess $proc -ErrorAction Stop } catch {}
}
Log "Defender exclusions set"

# --- uv -------------------------------------------------------------------
# Run Command executes as SYSTEM, so uv's installer drops uv into the SYSTEM
# profile, invisible to the interactive user. Install it, then copy uv/uvx to
# C:\tools\uv and put that on the machine PATH so any user finds it.
try {
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $uvSrc = "C:\Windows\System32\config\systemprofile\.local\bin"
    $uvDst = "C:\tools\uv"
    New-Item -ItemType Directory -Force -Path $uvDst | Out-Null
    Copy-Item "$uvSrc\uv.exe","$uvSrc\uvx.exe" -Destination $uvDst -Force -ErrorAction SilentlyContinue
    $mp = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($mp -notlike "*$uvDst*") { [Environment]::SetEnvironmentVariable("Path", "$mp;$uvDst", "Machine") }
    Log "uv installed to $uvDst"
} catch { Log "uv failed: $($_.Exception.Message)" }

# --- git ------------------------------------------------------------------
try {
    $gitExe = "$env:TEMP\git-installer.exe"
    Invoke-WebRequest "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe" -OutFile $gitExe -UseBasicParsing
    Start-Process $gitExe -ArgumentList "/VERYSILENT","/NORESTART" -Wait
    Log "git installed"
} catch { Log "git failed: $($_.Exception.Message)" }

# --- Atomic Red Team ------------------------------------------------------
# Non-interactive: pre-install NuGet and trust the gallery so Install-Module
# does not block on a confirmation prompt (which would hang Run Command).
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force -ErrorAction SilentlyContinue | Out-Null
    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted -ErrorAction SilentlyContinue
    Install-Module -Name invoke-atomicredteam -Scope AllUsers -Force -Confirm:$false -ErrorAction Stop
    IEX (IWR 'https://raw.githubusercontent.com/redcanaryco/invoke-atomicredteam/master/install-atomicredteam.ps1' -UseBasicParsing)
    Install-AtomicRedTeam -getAtomics -Force
    Log "Atomic Red Team installed"
} catch { Log "Atomic Red Team failed: $($_.Exception.Message)" }

# --- ngrok ----------------------------------------------------------------
try {
    New-Item -ItemType Directory -Force -Path "C:\ngrok" | Out-Null
    Invoke-WebRequest "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip" -OutFile "$env:TEMP\ngrok.zip" -UseBasicParsing
    Expand-Archive "$env:TEMP\ngrok.zip" -DestinationPath "C:\ngrok" -Force
    $mp = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($mp -notlike "*C:\ngrok*") { [Environment]::SetEnvironmentVariable("Path", "$mp;C:\ngrok", "Machine") }
    Log "ngrok installed"
} catch { Log "ngrok failed: $($_.Exception.Message)" }

# --- start-lab.ps1 (written for the analyst to run later) -----------------
$startLab = @'
param([string]$Token = "", [int]$Port = 8000)
if ([string]::IsNullOrWhiteSpace($Token)) {
    $Token = [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
}
Write-Host "=== MCP auth token (agent .env MCP_AUTH_TOKEN) ===" -ForegroundColor Cyan
Write-Host $Token; Write-Host ""
# Full paths, so this works regardless of PATH state. Each opens in its own
# titled window so you can watch the logs live.
$mcpCmd = "`$host.UI.RawUI.WindowTitle='MCP Server'; `$env:GIT_PYTHON_GIT_EXECUTABLE='C:\Program Files\Git\cmd\git.exe'; `$env:ART_EXECUTION_ENABLED='true'; `$env:ART_AUTH_TOKEN='$Token'; `$env:ART_MCP_TRANSPORT='streamable-http'; `$env:ART_MCP_HOST='127.0.0.1'; `$env:ART_MCP_PORT='$Port'; C:\tools\uv\uvx.exe --python 3.12 atomic-red-team-mcp"
Start-Process powershell -ArgumentList "-NoExit","-Command",$mcpCmd
Write-Host "MCP starting on 127.0.0.1:$Port (execution + auth)" -ForegroundColor Green
Start-Sleep -Seconds 5
# ngrok authenticates once per VM. If no authtoken is saved, ask for it and save
# it (stays in the ngrok config on the VM, never in git or Terraform).
$ngrokCfg = "$env:LOCALAPPDATA\ngrok\ngrok.yml"
if (-not (Test-Path $ngrokCfg) -or -not (Select-String -Path $ngrokCfg -Pattern 'authtoken' -Quiet)) {
    $nt = Read-Host "ngrok authtoken (from dashboard.ngrok.com, saved once)"
    & C:\ngrok\ngrok.exe config add-authtoken $nt.Trim()
}
$ngrokCmd = "`$host.UI.RawUI.WindowTitle='ngrok'; C:\ngrok\ngrok.exe http $Port"
Start-Process powershell -ArgumentList "-NoExit","-Command",$ngrokCmd
Start-Sleep -Seconds 5
try {
    $t = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -ErrorAction Stop
    $url = ($t.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
    if ($url) { Write-Host "=== ngrok URL (agent .env MCP_URL) ===" -ForegroundColor Cyan; Write-Host "$url/mcp" }
    else { Write-Host "ngrok up; open http://127.0.0.1:4040 for the URL." -ForegroundColor Yellow }
} catch { Write-Host "ngrok starting; open http://127.0.0.1:4040 for the URL." -ForegroundColor Yellow }
'@
Set-Content -Path "C:\lab\start-lab.ps1" -Value $startLab -Encoding UTF8
Log "start-lab.ps1 written to C:\lab\start-lab.ps1"

Log "provision finished"
Stop-Transcript | Out-Null
exit 0