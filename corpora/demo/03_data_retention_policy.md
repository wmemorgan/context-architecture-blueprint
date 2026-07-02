---
title: Aurora Platform — Data Retention Policy
author: Trust & Compliance
date: 2026-04-30
source: policy/retention
version: 1.4
---

# Aurora Platform — Data Retention Policy

The Aurora Platform processes documents to build collections. This policy states how long
data is kept.

## Source documents

Source documents ingested by a connector are retained for as long as the connector is
active. When a connector is removed, its source documents are purged within 30 days.

## Derived indexes

Derived search indexes are rebuilt from source documents and may be regenerated at any
time. They carry no independent retention obligation.

## Audit log

Workspace audit logs are retained for 12 months to support compliance review.
