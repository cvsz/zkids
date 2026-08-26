variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}

variable "cloudflare_account_id" {
  type        = string
  description = "Cloudflare account id owning the zeaz.dev zone."
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Cloudflare zone id for zeaz.dev."
}

variable "zkids_hostname" {
  type        = string
  default     = "zkids.zeaz.dev"
  description = "Public hostname served by the zkids factory dashboard."
}

variable "zkids_origin" {
  type        = string
  default     = "http://127.0.0.1:8010"
  description = "Loopback origin of the zkids web service."
}
