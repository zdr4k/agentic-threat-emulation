resource "azurerm_windows_virtual_machine" "lab" {
  name                  = "${var.prefix}-vm"
  resource_group_name   = azurerm_resource_group.lab.name
  location              = azurerm_resource_group.lab.location
  size                  = "Standard_B2s_v2"
  admin_username        = var.admin_username
  admin_password        = var.admin_password
  network_interface_ids = [azurerm_network_interface.vm.id]

  # System-assigned identity is required later so AMA can authenticate to Azure Monitor
  identity {
    type = "SystemAssigned"
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
  }

  source_image_reference {
    publisher = "MicrosoftWindowsDesktop"
    offer     = "Windows-11"
    sku       = "win11-24h2-pro"
    version   = "latest"
  }
}

# Sysmon install, script embedded inline (no external URL, repo stays private)
locals {
  sysmon_script = file("${path.module}/../scripts/install-sysmon.ps1")
}

resource "azurerm_virtual_machine_extension" "sysmon" {
  name                       = "install-sysmon"
  virtual_machine_id         = azurerm_windows_virtual_machine.lab.id
  publisher                  = "Microsoft.Compute"
  type                       = "CustomScriptExtension"
  type_handler_version       = "1.10"
  auto_upgrade_minor_version = true

  protected_settings = jsonencode({
    commandToExecute = "powershell -ExecutionPolicy Unrestricted -EncodedCommand ${textencodebase64(local.sysmon_script, "UTF-16LE")}"
  })
}