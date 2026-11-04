variable "subscription_id" { type = string } # secrets.tfvars
variable "location"        { type = string } # secrets.tfvars
variable "my_ip"           { type = string } # secrets.tfvars, your public IP as x.x.x.x/32

variable "admin_password" { # secrets.tfvars
  type      = string
  sensitive = true
}

variable "prefix" { # atomic purple team agent
  type    = string
  default = "apta"
}

variable "admin_username" {
  type    = string
  default = "labadmin"
}

variable "sysmon_script_url" { type = string } # raw URL of install-sysmon.ps1 in your repo
