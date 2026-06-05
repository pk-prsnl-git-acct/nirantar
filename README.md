# Nirantar

Public landing page for **Nirantar** and **The Still Signal**.

**Live site:** https://nirantar.xyz  
**Publication:** https://nirantar.substack.com

> Capability moves first. Institutions answer later. The Still Signal tracks the lag.

## About

Nirantar is a public web home for **The Still Signal** — a publication about AI capability, governance lag, institutional response, and the gaps that open when technology outruns response.

The site links to the Substack publication, highlights recent dispatches, and provides a simple branded entry point for the project.

## What this repo contains

```text
.
├── index.html          # Static GitHub Pages homepage
├── posts.json          # Latest post metadata used by the homepage
├── assets/             # Logo and social preview images
├── scripts/            # Utility scripts for post/feed updates
├── .github/workflows/  # GitHub Actions workflows
├── CNAME               # Custom domain configuration
└── README.md
```

## Publishing flow

The canonical publication lives on Substack:

https://nirantar.substack.com

The website at https://nirantar.xyz acts as the branded home page and latest-post preview. Post metadata is kept in `posts.json`, which the homepage can render into latest dispatch cards.

## Design notes

The visual direction is intentionally minimal, dark, and signal-led:

- dark editorial background
- luminous signal/radar motif
- concise typography
- clean external links to the full Substack archive and subscription flow

## Local editing

This is a simple static site.

To edit locally:

1. Clone the repo.
2. Open `index.html` in a browser.
3. Edit HTML/CSS directly.
4. Commit and push to `main`.

GitHub Pages publishes the site from the repository root.

## Domain

The custom domain is configured through the `CNAME` file:

```text
nirantar.xyz
```

DNS is managed separately through the domain provider.

## License

All writing, branding, and visual assets are © Nirantar unless otherwise noted.

The site code may be reused for learning or reference, but the **Nirantar** / **The Still Signal** branding, copy, logo, and publication assets should not be reused without permission.