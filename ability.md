---
name: ProtonMail Monitor
description: Background email monitoring for ProtonMail. Polls for new emails, notifies on mail from designated sender, auto-purges old emails. Requires platform IMAP support.
author: MultiClaw
version: 1.1.0
tags:
  - email
  - protonmail
  - imap
  - monitor
  - background
  - purge
triggers:
  - check mail
  - read email
  - check my email
  - do i have mail
  - new email
  - any mail
  - inbox
  - proton mail
config:
  proton_email:
    type: string
    required: true
    description: Your ProtonMail address
  designated_sender:
    type: string
    required: false
    description: Email address to monitor and act on
  poll_interval_minutes:
    type: integer
    default: 10
    description: How often to check for new mail
  purge_days:
    type: integer
    default: 31
    description: Auto-delete emails older than this many days
  mail_notifications:
    type: boolean
    default: true
    description: Play "you've got mail" chime
---

# ProtonMail Monitor Ability

Background email monitoring for ProtonMail.

## Features

- **Background Daemon**: Polls for new emails at regular intervals
- **Designated Sender**: Monitor specific sender for command emails
- **Auto-Purge**: Automatically deletes emails older than X days (default 31)
- **Voice Notifications**: "You've got mail" when new mail arrives

## Architecture

- `main.py` - Interactive skill (check status)
- `background.py` - Background daemon for polling

## Requirements

- Platform support for IMAP (currently blocked in sandbox)
- For production: either IMAP allowed or use ProtonMail HTTP API

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| poll_interval_minutes | 10 | Check frequency |
| purge_days | 31 | Auto-delete older emails |
| mail_notifications | true | Play chime |
