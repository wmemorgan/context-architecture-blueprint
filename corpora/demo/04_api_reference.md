---
title: Aurora Platform — API Reference
author: Platform Engineering
date: 2026-05-28
source: reference/api
version: 3.0
---

# Aurora Platform — API Reference

The Aurora Platform API lets you manage workspaces, connectors, and collections
programmatically. Terminology matches the product overview: workspace, connector,
collection.

## Authentication

All requests require a workspace API token. Tokens are scoped to a single workspace.

## Endpoints

- `GET /workspaces` — list workspaces.
- `POST /workspaces/{id}/connectors` — add a connector to a workspace.
- `GET /workspaces/{id}/collections` — list collections in a workspace.

## Rate limits

Each workspace token is limited to 600 requests per minute. Exceeding the limit returns a
`429` response with a retry-after header.
