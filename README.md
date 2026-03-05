# ProtonMail Ability

Send and receive ProtonMail emails through voice commands with OpenHome.

## Features

- **Send Email**: Compose and send emails via ProtonMail SMTP (interactive or one-shot mode)
- **Check Mail**: Actively check your inbox for new messages
- **"You've Got Mail" Notification**: Chime plays when new emails arrive (configurable)
- **Act on Email**: When email from designated sender arrives, parse body as voice command and execute
- **Auto-Reply**: If command produces a response, offer to reply via email

## Suggested Trigger Words

- send proton
- send protonmail
- check mail
- proton mail
- read email

## Setup

### 1. Generate ProtonMail App Password

1. Log into [ProtonMail](https://mail.protonmail.com)
2. Go to **Settings** → **Account** → **Security**
3. Under "Password & 2FA", click **Add App Password**
4. Create a new app password with **Mail** permission
5. Copy the generated password

### 2. Configure the Ability

Edit `config.json` (created by OpenHome when you upload) with your settings:

```json
{
    "unique_name": "proton-mail",
    "matching_hotwords": ["send proton", "send protonmail"],
    "smtp_password": "YOUR_APP_PASSWORD_HERE",
    "proton_email": "your.email@protonmail.com",
    "designated_sender": "your-trigger@email.com",
    "interactive_mode": true,
    "mail_notifications": true
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `smtp_password` | string | (required) | ProtonMail app password |
| `proton_email` | string | (required) | Your ProtonMail address |
| `designated_sender` | string | "" | Email address whose commands will be acted on |
| `interactive_mode` | boolean | true | If true, prompt for recipient→subject→body one at a time |
| `mail_notifications` | boolean | true | Play "you've got mail" chime when new email arrives |

## Usage

### Sending Email

**Interactive Mode** (default):
1. Say "send proton" or "send protonmail"
2. When asked "Who is this email going to?", respond with email address
3. When asked "What is the subject?", give your subject
4. When asked "What is the email body?", dictate your message
5. Review when prompted, then confirm or cancel

**One-Shot Mode**:
1. Set `interactive_mode: false` in config
2. Say "send proton"
3. Dictate recipient, subject, and body together
4. Answer follow-up questions for any missing info
5. Review and confirm before sending

### Checking Email

Say "check mail", "read email", or "check my inbox" to actively check for new messages.
- "You've got mail" chime plays if new mail exists (if enabled)
- Lists recent emails with sender and subject
- You can read any email body on demand

### Acting on Email (Remote Commands)

When `designated_sender` is configured:
1. Send an email from that address
2. When you "check mail", the ability detects it
3. Offers to "act on this email" — say yes
4. Agent parses your email body as a voice command
5. Executes the command and reports result
6. If the command produces a response, offers to reply via email

Example: Send email from designated sender with body "turn off the living room lights" → OpenHome executes → Offers to reply with confirmation

## Exit Phrases

Say any of these to cancel: stop, exit, quit, cancel, goodbye, done, never mind, forget it

The ability will confirm before exiting.

## Known Limitations

- **Passive polling TBD**: Currently only supports active "check mail" command. Background polling (automatic checks every N minutes) requires external scheduler or future platform support.

## Notes

- Requires a ProtonMail account with an app password
- Uses standard SMTP (port 587) and IMAP (port 993) protocols
- All emails are processed locally - no third-party forwarding
- The validator reports a false positive on `open()` in `register_capability()` — this is the required SDK pattern

## Author

MultiClaw / OpenHome Community