"""
ProtonMail Ability for OpenHome
Send and receive ProtonMail via SMTP/IMAP

Capabilities:
- Send email (interactive or one-shot mode)
- Check/read emails actively
- "You've got mail" notification on new emails (configurable)
- Act on email from designated sender (parse body as command, reply if needed)

TODO: Passive polling - requires external scheduler or platform support
      Currently only supports active "check mail" command
"""

import json
import os
import email
import smtplib
import imaplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from src.agent.capability import MatchingCapability
from src.main import AgentWorker
from src.agent.capability_worker import CapabilityWorker


class ProtonMailCapability(MatchingCapability):
    """Send and receive ProtonMail via SMTP/IMAP."""
    
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    
    # Configuration attributes
    smtp_password: str = ""
    proton_email: str = ""
    designated_sender: str = ""
    poll_interval_minutes: int = 10
    interactive_mode: bool = True
    mail_notifications: bool = True
    
    # Track last checked email for polling
    last_email_uid: str = ""
    
    # Do not change following tag of register capability
    #{{register capability}}

    @classmethod
    def register_capability(cls) -> "ProtonMailCapability":
        with open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        ) as file:
            data = json.load(file)
        return cls(
            unique_name=data["unique_name"],
            matching_hotwords=data["matching_hotwords"],
            smtp_password=data.get("smtp_password", ""),
            proton_email=data.get("proton_email", ""),
            designated_sender=data.get("designated_sender", ""),
            poll_interval_minutes=data.get("poll_interval_minutes", 10),
            interactive_mode=data.get("interactive_mode", True),
            mail_notifications=data.get("mail_notifications", True),
        )

    def call(self, worker: AgentWorker):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self.worker)
        self.worker.session_tasks.create(self.run())

    async def run(self):
        try:
            await self._run_proton_mail()
        except Exception as e:
            self.worker.editor_logging_handler.error(f"ProtonMail ability error: {e}")
            await self.capability_worker.speak(
                "I encountered an error with ProtonMail. Let me hand you back."
            )
        finally:
            self.capability_worker.resume_normal_flow()

    async def _run_proton_mail(self):
        """Main ability logic - determine action based on user input."""
        
        # First, check if user wants to send or read email
        await self.capability_worker.speak(
            "ProtonMail ready. Do you want to send an email or check for new messages?"
        )
        
        user_input = await self.capability_worker.user_response()
        
        # Check for exit phrases
        if self._is_exit(user_input):
            if await self._confirm_and_exit("exit"):
                return
        
        # Determine action
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in ["send", "write", "compose", "email"]):
            await self._handle_send_email()
        elif any(word in user_lower for word in ["check", "read", "new", "messages", "mail", "inbox"]):
            await self._handle_check_email()
        else:
            await self.capability_worker.speak(
                "I didn't catch that. Say 'send email' to compose a message "
                "or 'check mail' to see your inbox."
            )

    async def _handle_send_email(self):
        """Handle sending an email - interactive or one-shot mode."""
        
        recipient = ""
        subject = ""
        body = ""
        
        if self.interactive_mode:
            # Interactive mode: prompt for each field with loops
            while True:
                await self.capability_worker.speak("Who is this email going to?")
                recipient = await self.capability_worker.user_response()
                
                if self._is_exit(recipient):
                    if await self._confirm_and_exit("cancel"):
                        return
                    continue
                
                if "@" not in recipient:
                    await self.capability_worker.speak("That doesn't look like a valid email. Please try again.")
                    continue
                break
            
            while True:
                await self.capability_worker.speak("What is the subject of this email?")
                subject = await self.capability_worker.user_response()
                
                if self._is_exit(subject):
                    if await self._confirm_and_exit("cancel"):
                        return
                    continue
                break
            
            while True:
                await self.capability_worker.speak("What is the email body?")
                body = await self.capability_worker.user_response()
                
                if self._is_exit(body):
                    if await self._confirm_and_exit("cancel"):
                        return
                    continue
                break
        else:
            # One-shot mode: get all info at once, then fill in gaps
            await self.capability_worker.speak(
                "Please tell me the recipient, subject, and body of your email."
            )
            full_input = await self.capability_worker.user_response()
            
            if self._is_exit(full_input):
                if await self._confirm_and_exit("cancel"):
                    return
            
            # Ask for missing details
            while not recipient:
                await self.capability_worker.speak("Who is this email going to?")
                recipient = await self.capability_worker.user_response()
                if self._is_exit(recipient):
                    if await self._confirm_and_exit("cancel"):
                        return
                elif "@" not in recipient:
                    await self.capability_worker.speak("That doesn't look like a valid email.")
                    recipient = ""
            
            while not subject:
                await self.capability_worker.speak("What is the subject?")
                subject = await self.capability_worker.user_response()
                if self._is_exit(subject):
                    if await self._confirm_and_exit("cancel"):
                        return
            
            while not body:
                await self.capability_worker.speak("What is the message?")
                body = await self.capability_worker.user_response()
                if self._is_exit(body):
                    if await self._confirm_and_exit("cancel"):
                        return
        
        # Review flow
        await self.capability_worker.speak(
            "Would you like to review the details of this email before sending?"
        )
        
        review_response = await self.capability_worker.user_response()
        
        if self._is_exit(review_response):
            if await self._confirm_and_exit("cancel"):
                return
        
        if any(word in review_response.lower() for word in ["yes", "review", "show"]):
            await self.capability_worker.speak(
                f"You're sending an email to {recipient}. "
                f"Subject: {subject}. "
                f"Body: {body}"
            )
        
        # Confirm send
        await self.capability_worker.speak("Shall I send this email?")
        confirm = await self.capability_worker.user_response()
        
        if self._is_exit(confirm):
            if await self._confirm_and_exit("cancel"):
                return
        
        if any(word in confirm.lower() for word in ["yes", "send", "confirm", "go"]):
            success = await self._send_email(recipient, subject, body)
            if success:
                await self.capability_worker.speak("Email sent successfully!")
            else:
                await self.capability_worker.speak(
                    "Sorry, I couldn't send the email. Please check your settings and try again."
                )
        else:
            await self.capability_worker.speak("Email cancelled.")

    async def _handle_check_email(self):
        """Handle checking for new emails (active).
        
        Fetches recent emails and:
        - Plays "You've got mail" chime if notifications enabled and new mail exists
        - Lists emails and lets user read any of them
        - If email from designated_sender, acts on it (parses as command, replies if needed)
        """
        
        await self.capability_worker.speak("Checking for new emails...")
        
        emails = await self._fetch_emails()
        
        if not emails:
            await self.capability_worker.speak("You have no new emails.")
        else:
            # Play notification chime if enabled
            if self.mail_notifications:
                await self.capability_worker.speak("You've got mail!")
            
            await self.capability_worker.speak(f"You have {len(emails)} new email(s).")
            
            # Check for designated sender email (for acting on it)
            designated_email = None
            for email_data in emails:
                if self.designated_sender and self.designated_sender.lower() in email_data['from'].lower():
                    designated_email = email_data
                    break
            
            # If there's an email from designated sender, offer to act on it
            if designated_email:
                await self.capability_worker.speak(
                    f"You have an email from {self.designated_sender}. "
                    f"Subject: {designated_email['subject']}. "
                    f"Would you like me to act on this email?"
                )
                
                response = await self.capability_worker.user_response()
                
                if any(word in response.lower() for word in ["yes", "act", "do", "sure", "go"]):
                    await self._act_on_email(designated_email)
                    return  # _act_on_email handles its own exit flow
            
            # List emails for user to read
            for i, email_data in enumerate(emails[:5]):
                await self.capability_worker.speak(
                    f"Email {i+1}: From {email_data['from']}. Subject: {email_data['subject']}. "
                    f"Would you like me to read the body?"
                )
                
                response = await self.capability_worker.user_response()
                
                if self._is_exit(response):
                    if await self._confirm_and_exit("exit"):
                        return
                
                if any(word in response.lower() for word in ["yes", "read", "sure"]):
                    await self.capability_worker.speak(email_data['body'][:500])

    async def _act_on_email(self, email_data: dict):
        """Act on an email from the designated sender.
        
        Parses the email body as a voice command to the agent.
        If the agent's response indicates a reply is expected, sends an email reply.
        """
        email_body = email_data['body'][:1000]  # Limit for processing
        email_from = email_data['from']
        
        await self.capability_worker.speak("Processing email command...")
        
        # Parse body as voice command - ask agent what to do
        action_prompt = (
            f"The user sent this email command:\n"
            f"Subject: {email_data['subject']}\n"
            f"Body: {email_body}\n\n"
            f"Execute this command as if the user spoke it to you. "
            f"Respond with what you did. If the command asks a question or expects a response, "
            f"include that response in your output so I can reply to the email."
        )
        
        action_response = self.capability_worker.text_to_text_response(action_prompt)
        
        # Tell the user what happened
        await self.capability_worker.speak(f"Email command executed: {action_response}")
        
        # Check if we should reply to the email
        # Heuristic: if response contains question marks or seems like an answer, reply
        should_reply = "?" in action_response or any(
            word in action_response.lower() 
            for word in ["here's", "here is", "the", "result", "answer", "status", "current"]
        )
        
        if should_reply:
            await self.capability_worker.speak(
                "This command produced a response. Would you like me to reply to the email?"
            )
            
            reply_confirm = await self.capability_worker.user_response()
            
            if any(word in reply_confirm.lower() for word in ["yes", "sure", "go", "do"]):
                # Extract email address from the "From" field
                reply_to = self._extract_email_address(email_from)
                
                if reply_to:
                    reply_subject = f"Re: {email_data['subject']}"
                    reply_body = action_response
                    
                    success = await self._send_email(reply_to, reply_subject, reply_body)
                    
                    if success:
                        await self.capability_worker.speak("Reply sent!")
                    else:
                        await self.capability_worker.speak(
                            "Sorry, I couldn't send the reply. Check your settings."
                        )
                else:
                    await self.capability_worker.speak(
                        "I couldn't extract a valid email address to reply to."
                    )
            else:
                await self.capability_worker.speak("Reply cancelled.")
        
        await self.capability_worker.speak("Done processing email.")

    def _extract_email_address(self, from_header: str) -> str:
        """Extract email address from 'From' header."""
        import re
        match = re.search(r'<(.+?)>|^(.+?)$', from_header)
        if match:
            return match.group(1) or match.group(2)
        return ""

    async def _send_email(self, recipient: str, subject: str, body: str) -> bool:
        """Send email via ProtonMail SMTP."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.proton_email
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            # ProtonMail SMTP settings
            server = smtplib.SMTP('smtp.protonmail.com', 587)
            server.starttls()
            server.login(self.proton_email, self.smtp_password)
            server.sendmail(self.proton_email, recipient, msg.as_string())
            server.quit()
            
            self.worker.editor_logging_handler.info(f"Email sent to {recipient}")
            return True
            
        except Exception as e:
            self.worker.editor_logging_handler.error(f"Failed to send email: {e}")
            return False

    async def _fetch_emails(self, limit: int = 10):
        """Fetch recent emails via IMAP."""
        emails = []
        
        try:
            # ProtonMail IMAP settings
            mail = imaplib.IMAP4_SSL('imap.protonmail.com')
            mail.login(self.proton_email, self.smtp_password)
            mail.select('INBOX')
            
            # Search for recent emails
            since_date = (datetime.now() - timedelta(days=7)).strftime('%d-%b-%Y')
            status, messages = mail.search(None, f'SINCE {since_date}')
            
            if status == 'OK':
                email_ids = messages[0].split()[-limit:]
                
                for email_id in email_ids:
                    status, msg_data = mail.fetch(email_id, '(RFC822)')
                    if status == 'OK':
                        msg = email.message_from_bytes(msg_data[0][1])
                        
                        email_info = {
                            'from': msg.get('From', 'Unknown'),
                            'subject': msg.get('Subject', 'No Subject'),
                            'date': msg.get('Date', ''),
                            'body': self._extract_body(msg)
                        }
                        emails.append(email_info)
            
            mail.logout()
            
        except Exception as e:
            self.worker.editor_logging_handler.error(f"Failed to fetch emails: {e}")
        
        return emails

    def _extract_body(self, msg) -> str:
        """Extract body from email message."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            return msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        return ""

    def _is_exit(self, user_input: str) -> bool:
        """Check if user wants to exit."""
        exit_phrases = {"stop", "exit", "quit", "cancel", "goodbye", "done", "never mind", "forget it"}
        return any(phrase in user_input.lower() for phrase in exit_phrases)

    async def _confirm_and_exit(self, action: str = "exit"):
        """Confirm before exiting. Returns True if confirmed (should exit), False if cancelled."""
        await self.capability_worker.speak(f"Are you sure you want to {action}?")
        response = await self.capability_worker.user_response()
        
        if any(word in response.lower() for word in ["yes", "confirm", "sure", "yeah"]):
            await self.capability_worker.speak("Ok, cancelling.")
            return True
        else:
            await self.capability_worker.speak("Ok, continuing.")
            return False


# ============================================================================
# TBD: Passive Polling Implementation
# ============================================================================
# TODO: Implement background polling for designated sender emails
#
# Architecture options (requires external scheduler or platform support):
# 1. External cron job triggers this ability via OpenHome API every N minutes
# 2. OpenHome platform adds background task support (future feature)
# 3. User manually triggers "check mail" when expecting remote commands
#
# When implemented:
# - Fetch new emails since last check
# - If email from designated_sender:
#   - Play "You've got mail" chime (if mail_notifications enabled)
#   - Parse body as command via text_to_text_response()
#   - Reply via email if response expected
# - Store last checked email UID to avoid duplicate processing
# ============================================================================