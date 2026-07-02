# Off-network access for the dashboard - Tailscale (Joseph, ~15 min)

The dashboard runs on this PC and is reachable on the office LAN at
http://10.1.10.109:8765. To reach it from anywhere (the Owner's phone,
home), use Tailscale. It needs two human steps Cowork cannot do:
a Windows admin (UAC) prompt and an interactive account login.

## Steps

1. Installer is already downloaded at `%TEMP%\tailscale.msi`
   (also available via `winget install Tailscale.Tailscale`). Run it and
   click Yes on the Windows permission prompt.
2. A browser opens. Sign in to Tailscale with the Your Company Google
   account (yourcompanyjoseph@gmail.com is fine). This creates the
   tailnet.
3. Install Tailscale on the Owner's phone and laptop. Sign in with the
   SAME account so they join the same tailnet.
4. On this PC, run `tailscale ip -4` to get its tailnet IP (100.x.y.z).
5. Owner opens `http://100.x.y.z:8765` from any device, enters the
   dashboard token once. Done. No ports opened on the router, no public
   exposure.

## Why not just port-forward

yourcompany.example.com was compromised last week. We do not expose this PC to
the public internet. Tailscale is identity-based and encrypted, only
devices signed into the tailnet can reach it.

## Token

Dashboard access token is in `web_dashboard/.token`. Share only with
Owner and Joseph. To rotate: delete that file, restart the server,
the new token prints to the server console once.

## Optional hardening later

Tailscale ACLs can restrict port 8765 to just the Owner's and Joseph's
devices. Cloudflare Tunnel + Access on office.yourcompany.example.com is the
browser-only alternative if a client app on the phone is unwanted.
