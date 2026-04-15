#!/usr/bin/env bash
# Sovereign network defaults for K1 startup/runtime.
# Values here act as defaults only; .env values take precedence.

: "${K1_ENFORCE_SOVEREIGN_NETWORK:=true}"
: "${K1_ALLOW_INSECURE_LOCAL_START:=false}"
: "${K1_VPN_ALLOWED_INTERFACES:=tun*,wg*,vpn*,snl*}"
: "${K1_VPN_BRIDGE_INTERFACE:=}"
: "${K1_ACTIVE_VPN_INTERFACE:=}"
: "${K1_VPN_CHECK_IP:=1.1.1.1}"
: "${K1_EGRESS_IP_API:=https://ipinfo.io/ip}"
: "${K1_LOCAL_ISP_CIDRS:=}"
: "${K1_USE_PROXIES:=false}"
: "${K1_RESIDENTIAL_PROXY_URL:=}"
: "${K1_PROXY_HEALTHCHECK_URL:=https://example.com}"
: "${K1_PROXY_HEAD_TIMEOUT_SECONDS:=10}"

export K1_ENFORCE_SOVEREIGN_NETWORK
export K1_ALLOW_INSECURE_LOCAL_START
export K1_VPN_ALLOWED_INTERFACES
export K1_VPN_BRIDGE_INTERFACE
export K1_ACTIVE_VPN_INTERFACE
export K1_VPN_CHECK_IP
export K1_EGRESS_IP_API
export K1_LOCAL_ISP_CIDRS
export K1_USE_PROXIES
export K1_RESIDENTIAL_PROXY_URL
export K1_PROXY_HEALTHCHECK_URL
export K1_PROXY_HEAD_TIMEOUT_SECONDS
