"""
ProtonMail Ability for OpenHome
Send and receive ProtonMail via SMTP/IMAP

Capabilities:
- Send email (interactive or one-shot mode)
- Check/read emails actively
- "You've got mail" notification on new emails (configurable)
- Act on email from designated sender (parse body as command, reply if needed)
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
            await self.capability_worker.speak("I encountered an error. Let me hand you back.")
        finally:
            self.capability_worker.resume_normal_flow()

    async def _run_proton_mail(self):
        """Main ability logic - read trigger context and route appropriately."""
        
        # Read trigger context from conversation history
        history = self.capability_worker.get_full_message_history()
        trigger_intent = self._classify_trigger_intent(history)
        
        # Route based on detected intent
        if trigger_intent == "send":
            await self._handle_send_email(from_trigger=True)
        elif trigger_intent == "check" or trigger_intent == "read":
            await self._handle_check_email(from_trigger=True)
        else:
            # Default: ask what they want
            await self.capability_worker.speak("Send email or check mail?")
            user_input = await self.capability_worker.user_response()
            
            if self._is_exit(user_input):
                if await self._confirm_and_exit("exit"):
                    return
            
            user_lower = user_input.lower()
            
            if any(word in user_lower for word in ["send", "write", "compose"]):
                await self._handle_send_email(from_trigger=False)
            elif any(word in user_lower for word in ["check", "read", "new", "mail", "inbox"]):
                await self._handle_check_email(from_trigger=False)
            else:
                await self.capability_worker.speak("I didn't catch that. Say send or check.")

    def _classify_trigger_intent(self, history: list) -> str:
        """Classify intent from trigger context using conversation history."""
        if not history:
            return "unknown"
        
        # Get last few messages
        recent = history[-5:] if len(history) > 5 else history
        
        # Build trigger text
        trigger_text = " ".join([
            msg.get("content", "").lower() 
            for msg in recent 
            if msg.get("role") == "user"
        ])
        
        # Classify intent
        send_keywords = ["send", "write", "compose", "email to", "mail to", "proton"]
        check_keywords = ["check", "read", "new", "inbox", "do i have", "any mail"]
        
        if any(kw in trigger_text for kw in send_keywords):
            return "send"
        elif any(kw in trigger_text for kw in check_keywords):
            return "check"
        
        return "unknown"

    async def _handle_send_email(self, from_trigger: bool = False):
        """Handle sending an email - interactive or one-shot mode."""
        
        recipient = ""
        subject = ""
        body = ""
        
        if self.interactive_mode:
            # Interactive mode: prompt for each field with loops
            while True:
                if not from_trigger:
                    await self.capability_worker.speak("Who to?")
                recipient = await self.capability_worker.user_response()
                
                if self._is_exit(recipient):
                    if await self._confirm_and_exit("cancel"):
                        return
                    continue
                
                if "@" not in recipient:
                    await self.capability_worker.speak("That doesn't look like an email.")
                    continue
                break
            
            while True:
                await self.capability_worker.speak("Subject?")
                subject = await self.capability_worker.user_response()
                
                if self._is_exit(subject):
                    if await self._confirm_and_exit("cancel"):
                        return
                    continue
                break
            
            while True:
                await self.capability_worker.speak("What's the message?")
                body = await self.capability_worker.user_response()
                
                if self._is_exit(body):
                    if await self._confirm_and_exit("cancel"):
                        return
                    continue
                break
        else:
            # One-shot mode: get all info at once
            await self.capability_worker.speak("Recipient, subject, and message?")
            full_input = await self.capability_worker.user_response()
            
            if self._is_exit(full_input):
                if await self._confirm_and_exit("cancel"):
                    return
            
            # Ask for missing details
            while not recipient:
                await self.capability_worker.speak("Who to?")
                recipient = await self.capability_worker.user_response()
                if self._is_exit(recipient):
                    if await self._confirm_and_exit("cancel"):
                        return
                elif "@" not in recipient:
                    await self.capability_worker.speak("Need a valid email.")
                    recipient = ""
            
            while not subject:
                await self.capability_worker.speak("Subject?")
                subject = await self.capability_worker.user_response()
                if self._is_exit(subject):
                    if await self._confirm_and_exit("cancel"):
                        return
            
            while not body:
                await self.capability_worker.speak("Message?")
                body = await self.capability_worker.user_response()
                if self._is_exit(body):
                    if await self._confirm_and_exit("cancel"):
                        return
        
        # Review - keep it short
        await self.capability_worker.speak(f"To: {recipient}. Subject: {subject}. Send?")
        
        confirm = await self.capability_worker.user_response()
        
        if self._is_exit(confirm):
            if await self._confirm_and_exit("cancel"):
                return
        
        if any(word in confirm.lower() for word in ["yes", "send", "confirm", "go", "sure"]):
            await self.capability_worker.speak("Sending...")
            success = await self._send_email(recipient, subject, body)
            if success:
                await self.capability_worker.speak("Sent!")
            else:
                await self.capability_worker.speak("Failed. Check settings.")
        else:
            await self.capability_worker.speak("Cancelled.")

    async def _handle_check_email(self, from_trigger: bool = False):
        """Handle checking for new emails (active)."""
        
        if not from_trigger:
            await self.capability_worker.speak("Checking mail...")
        else:
            await self.capability_worker.speak("One sec, checking your mail...")
        
        emails = await self._fetch_emails()
        
        if not emails:
            await self.capability_worker.speak("No new mail.")
        else:
            if self.mail_notifications:
                await self.capability_worker.speak("You've got mail!")
            
            await self.capability_worker.speak(f"{len(emails)} new. Want me to read them?")
            
            response = await self.capability_worker.user_response()
            
            if self._is_exit(response):
                if await self._confirm_and_exit("exit"):
                    return
            
            if any(word in response.lower() for word in ["yes", "sure", "go", "read"]):
                for i, email_data in enumerate(emails[:3]):
                    await self.capability_worker.speak(
                        f"From {email_data['from']}. Subject: {email_data['subject']}."
                    )

    async def _act_on_email(self, email_data: dict):
        """Act on an email from the designated sender."""
        email_body = email_data['body'][:1000]
        
        await self.capability_worker.speak("Processing command...")
        
        action_prompt = (
            f"User sent this email command:\n"
            f"Subject: {email_data['subject']}\n"
            f"Body: {email_body}\n\n"
            f"Execute this command. If it asks a question, include the answer."
        )
        
        action_response = self.capability_worker.text_to_text_response(action_prompt)
        
        await self.capability_worker.speak(f"Done. {action_response}")
        
        # Check if we should reply
        should_reply = "?" in action_response or len(action_response) > 50
        
        if should_reply:
            reply_confirm = await self.capability_worker.run_confirmation_loop(
                "Send reply?"
            )
            
            if reply_confirm:
                reply_to = self._extract_email_address(email_data['from'])
                if reply_to:
                    success = await self._send_email(
                        reply_to, 
                        f"Re: {email_data['subject']}", 
                        action_response
                    )
                    await self.capability_worker.speak("Reply sent!" if success else "Reply failed.")
                else:
                    await self.capability_worker.speak("Couldn't extract reply address.")
            else:
                await self.capability_worker.speak("Reply skipped.")

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
            mail = imaplib.IMAP4_SSL('imap.protonmail.com')
            mail.login(self.proton_email, self.smtp_password)
            mail.select('INBOX')
            
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
        exit_phrases = {"stop", "exit", "quit", "cancel", "goodbye", "done", "never mind"}
        return any(phrase in user_input.lower() for phrase in exit_phrases)

    async def _confirm_and_exit(self, action: str = "exit"):
        """Confirm before exiting. Returns True if confirmed."""
        confirmed = await self.capability_worker.run_confirmation_loop(
            f"Confirm {action}?"
        )
        
        if confirmed:
            await self.capability_worker.speak("Okay.")
            return True
        else:
            await self.capability_worker.speak("Continuing.")
            return False
