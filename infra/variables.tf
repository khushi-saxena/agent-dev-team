variable "tenancy_ocid" { type = string }
variable "user_ocid" { type = string }
variable "fingerprint" { type = string }
variable "private_key_path" { type = string }
variable "compartment_ocid" { type = string }

variable "region" {
  type        = string
  description = "your home region, e.g. us-sanjose-1"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "ssh_allowed_cidr" {
  type        = string
  description = "lock this to your IP/32 if you can"
  default     = "0.0.0.0/0"
}

# switch AD if you get "Out of host capacity"
variable "ad_index" {
  type    = number
  default = 0
}

# drop to 1 / 6 if capacity is tight
variable "ocpus" {
  type    = number
  default = 2
}

variable "memory_gb" {
  type    = number
  default = 12
}
