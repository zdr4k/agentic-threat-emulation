resource "azurerm_windows_virtual_machine" "lab" {
  name                  = "${var.prefix}-vm"
  resource_group_name   = azurerm_resource_group.lab.name
  location              = azurerm_resource_group.lab.location
  size                  = "Standard_B2s"
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
    sku       = "win11-23h2-pro"
    version   = "latest"
  }
}

# The Sysmon extension: runs install-sysmon.ps1 inside the VM
resource "azurerm_virtual_machine_extension" "sysmon" {
  name                       = "install-sysmon"
  virtual_machine_id         = azurerm_windows_virtual_machine.lab.id
  publisher                  = "Microsoft.Compute"
  type                       = "CustomScriptExtension"
  type_handler_version       = "1.10"
  auto_upgrade_minor_version = true

  settings = jsonencode({
    fileUris         = [var.sysmon_script_url]
    commandToExecute = "powershell -ExecutionPolicy Unrestricted -File install-sysmon.ps1"
  })
}

resource "azurerm_dev_test_global_vm_shutdown_schedule" "lab" {
  virtual_machine_id = azurerm_windows_virtual_machine.lab.id
  location           = azurerm_resource_group.lab.location
  enabled            = true

  daily_recurrence_time = "2000"           # 20:00
  timezone              = "W. Europe Standard Time"

  notification_settings {
    enabled = false
  }
}