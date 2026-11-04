# Existing Sentinel workspace, referenced not created
data "azurerm_log_analytics_workspace" "sentinel" {
  name                = "log-analyst-de-lab"
  resource_group_name = "rg-de-lab"   # confirm the exact RG name
}

# Azure Monitor Agent on the VM
resource "azurerm_virtual_machine_extension" "ama" {
  name                       = "AzureMonitorWindowsAgent"
  virtual_machine_id         = azurerm_windows_virtual_machine.lab.id
  publisher                  = "Microsoft.Azure.Monitor"
  type                       = "AzureMonitorWindowsAgent"
  type_handler_version       = "1.0"
  auto_upgrade_minor_version = true
  automatic_upgrade_enabled  = true
}

# Data Collection Rule: what to collect and where to send it
resource "azurerm_monitor_data_collection_rule" "lab" {
  name                = "${var.prefix}-dcr"
  resource_group_name = azurerm_resource_group.lab.name
  location            = data.azurerm_log_analytics_workspace.sentinel.location

  destinations {
    log_analytics {
      workspace_resource_id = data.azurerm_log_analytics_workspace.sentinel.id
      name                  = "sentinel-dest"
    }
  }

  # Sysmon operational channel
  data_sources {
    windows_event_log {
      name    = "sysmon-events"
      streams = ["Microsoft-Event"]
      x_path_queries = [
        "Microsoft-Windows-Sysmon/Operational!*"
      ]
    }

    # Standard Windows security + system events
    windows_event_log {
      name    = "security-events"
      streams = ["Microsoft-Event"]
      x_path_queries = [
        "Security!*[System[(band(Keywords,13510798882111488))]]",
        "System!*"
      ]
    }
  }

  data_flow {
    streams      = ["Microsoft-Event"]
    destinations = ["sentinel-dest"]
  }

  depends_on = [azurerm_virtual_machine_extension.ama]
}

# Associate the DCR with the VM
resource "azurerm_monitor_data_collection_rule_association" "lab" {
  name                    = "${var.prefix}-dcr-assoc"
  target_resource_id      = azurerm_windows_virtual_machine.lab.id
  data_collection_rule_id = azurerm_monitor_data_collection_rule.lab.id
}