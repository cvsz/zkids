output "hostname" {
  value       = "https://${var.zkids_hostname}"
  description = "Public URL of the zkids factory dashboard."
}

output "tunnel_id" {
  value       = cloudflare_zero_trust_tunnel_cloudflared.zkids.id
  description = "Id of the dedicated zkids tunnel."
}

output "connector_token_command" {
  value       = "curl -s -H \"Authorization: Bearer $CF_API_TOKEN\" https://api.cloudflare.com/client/v4/accounts/${var.cloudflare_account_id}/cfd_tunnel/${cloudflare_zero_trust_tunnel_cloudflared.zkids.id}/token"
  description = "Fetch the cloudflared connector token for systemd."
}
