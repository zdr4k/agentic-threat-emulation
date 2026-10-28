# scripts/install-sysmon.ps1
# Installs Sysmon with a public modular config. Runs as the Custom Script Extension payload.
$ErrorActionPreference = "Stop"

$workDir = "C:\lab\sysmon"
New-Item -ItemType Directory -Force -Path $workDir | Out-Null

# Idempotent: skip if Sysmon is already running
if (Get-Service -Name "Sysmon64" -ErrorAction SilentlyContinue) {
    Write-Output "Sysmon already installed, nothing to do."
    exit 0
}

# Download Sysmon from Sysinternals
$sysmonZip = "$workDir\Sysmon.zip"
Invoke-WebRequest -Uri "https://download.sysinternals.com/files/Sysmon.zip" -OutFile $sysmonZip
Expand-Archive -Path $sysmonZip -DestinationPath $workDir -Force

# Download a modular baseline config (SwiftOnSecurity)
$configPath = "$workDir\sysmonconfig.xml"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/SwiftOnSecurity/sysmon-config/master/sysmonconfig-export.xml" -OutFile $configPath

# Install with the config
& "$workDir\Sysmon64.exe" -accepteula -i $configPath
Write-Output "Sysmon installed."