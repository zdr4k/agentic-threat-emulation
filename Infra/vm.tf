resource "azurerm_windows_virtual_machine" "lab" {
  name                  = "${var.prefix}-vm"
  resource_group_name   = azurerm_resource_group.lab.name
  location              = azurerm_resource_group.lab.location
  size                  = "Standard_B2s_v2"
  admin_username        = var.admin_username
  admin_password        = var.admin_password
  network_interface_ids = [azurerm_network_interface.vm.id]

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

resource "azurerm_virtual_machine_run_command" "provision" {
  name               = "provision"
  location           = azurerm_resource_group.lab.location
  virtual_machine_id = azurerm_windows_virtual_machine.lab.id

  source {
    script = file("${path.module}/../Scripts/provision.ps1")
  }
}