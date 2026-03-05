---
name: ProtonMail
description: Send and receive ProtonMail emails via voice commands. Check inbox, compose and send emails, get notified of new mail, and act on emails from designated senders as voice commands.
author: MultiClaw
version: 1.0.0
tags:
  - email
  - protonmail
  - smtp
  - imap
  - communication
triggers:
  - send proton
  - send protonmail
  - proton mail
  - check mail
  - read email
  - check my email
  - do i have mail
  - new email
  - any mail
  - inbox
  - compose email
  - write email
  - send email
config:
  smtp_password:
    type: string
    required: true
    description: ProtonMail app password
  proton_email:
    type: string
    required: true
    description: Your ProtonMail address
  designated_sender:
    type: string
    required: false
    description: Email address whose commands will be acted on
  interactive_mode:
    type: boolean
    default: true
    description: Interactive prompts vs one-shot
  mail_notifications:
    type: boolean
    default: true
    description: Play "you've got mail" chime
---

# ProtonMail Ability

Voice-controlled email via ProtonMail.

## Features

- **Send Email**: Compose and send via SMTP
- **Check Mail**: Fetch recent emails from IMAP
- **Notifications**: "You've got mail" chime when new mail arrives
- **Act on Commands**: Emails from designated sender are parsed as voice commands

## Usage

Say "send proton" to compose, "check mail" to view inbox.
