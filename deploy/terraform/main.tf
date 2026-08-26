resource "random_password" "zkids_tunnel_secret" {
  length  = 64
  special = false
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "zkids" {
  account_id    = var.cloudflare_account_id
  name          = "zkids-tunnel"
  tunnel_secret = random_password.zkids_tunnel_secret.result
  config_src    = "cloudflare"
}

locals {
  zkids_tunnel_cname = "${cloudflare_zero_trust_tunnel_cloudflared.zkids.id}.cfargotunnel.com"
}

# The tunnel configuration is owned entirely by this stack: one hostname,
# one loopback origin, terminal 404 fallback.
resource "cloudflare_zero_trust_tunnel_cloudflared_config" "zkids" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.zkids.id
  source     = "cloudflare"

  config = {
    ingress = [
      {
        hostname = var.zkids_hostname
        service  = var.zkids_origin
      },
      {
        service = "http_status:404"
      },
    ]
  }
}

resource "cloudflare_dns_record" "zkids" {
  zone_id = var.cloudflare_zone_id
  name    = var.zkids_hostname
  type    = "CNAME"
  content = local.zkids_tunnel_cname
  ttl     = 1
  proxied = true

  comment = "AI Kids Cartoon Factory via dedicated Cloudflare Tunnel - managed by Terraform (zkid repo)"
}
