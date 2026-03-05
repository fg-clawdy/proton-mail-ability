"""
Background Daemon for ProtonMail Ability
Polls for new emails from designated sender at regular intervals
"""

import json
import os
import email
import imaplib
from datetime import datetime, timedelta

from src.agent.capability import MatchingCapability
from src.main import AgentWorker
from src.agent.capability_worker import CapabilityWorker


class ProtonMailDaemon(MatchingCapability):
    """Background daemon for passive ProtonMail monitoring."""
    
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    background_daemon_mode: bool = False
    
    # Configuration
    smtp_password: str = ""
    proton_email: str = ""
    designated_sender: str = ""
    poll_interval_minutes: int = 10
    mail_notifications: bool = True
    
    # Track processed emails
    processed_uids: set = set()
    
    # Do not change following tag of register capability
    #{{register capability}}

    @classmethod
    def register_capability(cls) -> "ProtonMailDaemon":
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
            mail_notifications=data.get("mail_notifications", True),
        )

    def call(self, worker: AgentWorker, background_daemon_mode: bool = False):
        self.worker = worker
        self.background_daemon_mode = background_daemon_mode
        self.capability_worker = CapabilityWorker(self.worker)
        self.worker.session_tasks.create(self.background_loop())

    async def background_loop(self):
        """Continuous background polling loop."""
        self.worker.editor_logging_handler.info(
            f"ProtonMail daemon started. Polling every {self.poll_interval_minutes} minutes."
        )
        
        # Load previously processed UIDs
        await self._load_processed_uids()
        
        try:
            while True:
                await self._check_for_designated_sender_emails()
                await self.worker.session_tasks.sleep(self.poll_interval_minutes * 60)
        except Exception as e:
            self.worker.editor_logging_handler.error(f"Daemon error: {e}")
            await self.capability_worker.speak("Mail daemon encountered an error.")

    async def _check_for_designated_sender_emails(self):
        """Check for new emails from designated sender."""
        if not self.designated_sender:
            return
        
        try:
            emails = await self._fetch_emails(limit=10)
            
            for email_data in emails:
                # Create unique ID for this email
                email_uid = f"{email_data['from']}:{email_data['subject']}:{email_data['date']}"
                
                if email_uid in self.processed_uids:
                    continue
                
                # Check if from designated sender
                if self.designated_sender.lower() in email_data['from'].lower():
                    self.worker.editor_logging_handler.info(
                        f"Command email from {self.designated_sender}"
                    )
                    
                    # Interrupt current output and notify
                    await self.capability_worker.send_interrupt_signal()
                    
                    if self.mail_notifications:
                        await self.capability_worker.speak("You've got mail!")
                    
                    # Process the command
                    await self._act_on_email(email_data)
                    
                    # Mark as processed
                    self.processed_uids.add(email_uid)
                    await self._save_processed_uids()
                    
        except Exception as e:
            self.worker.editor_logging_handler.error(f"Error checking emails: {e}")

    async def _act_on_email(self, email_data: dict):
        """Act on email from designated sender."""
        email_body = email_data['body'][:1000]
        
        await self.capability_worker.speak("Processing email command...")
        
        action_prompt = (
            f"User sent this email command:\n"
            f"Subject: {email_data['subject']}\n"
            f"Body: {email_body}\n\n"
            f"Execute this command. If it asks a question, include the answer."
        )
        
        action_response = self.capability_worker.text_to_text_response(action_prompt)
        
        await self.capability_worker.speak(f"Done. {action_response}")
        
        # Auto-reply with result
        reply_to = self._extract_email_address(email_data['from'])
        if reply_to:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            try:
                msg = MIMEMultipart()
                msg['From'] = self.proton_email
                msg['To'] = reply_to
                msg['Subject'] = f"Re: {email_data['subject']}"
                msg.attach(MIMEText(action_response, 'plain'))
                
                server = smtplib.SMTP('smtp.protonmail.com', 587)
                server.starttls()
                server.login(self.proton_email, self.smtp_password)
                server.sendmail(self.proton_email, reply_to, msg.as_string())
                server.quit()
                
                await self.capability_worker.speak("Reply sent.")
            except Exception as e:
                self.worker.editor_logging_handler.error(f"Auto-reply failed: {e}")

    def _extract_email_address(self, from_header: str) -> str:
        import re
        match = re.search(r'<(.+?)>|^(.+?)$', from_header)
        return match.group(1) or match.group(2) if match else ""

    async def _fetch_emails(self, limit: int = 10):
        """Fetch recent emails via IMAP."""
        emails = []
        
        try:
            mail = imaplib.IMAP4_SSL('imap.protonmail.com')
            mail.login(self.proton_email, self.smtp_password)
            mail.select('INBOX')
            
            since_date = (datetime.now() - timedelta(days=1)).strftime('%d-%b-%Y')
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
            self.worker.editor_logging_handler.error(f"IMAP error: {e}")
        
        return emails

    def _extract_body(self, msg) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            return msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        return ""

    async def _load_processed_uids(self):
        """Load processed email UIDs from storage."""
        exists = await self.capability_worker.check_if_file_exists(
            "protonmail_processed.json"
        )
        if exists:
            content = await self.capability_worker.read_file("protonmail_processed.json")
            if content:
                import json
                try:
                    data = json.loads(content)
                    self.processed_uids = set(data.get("uids", []))
                except:
                    pass

    async def _save_processed_uids(self):
        """Save processed email UIDs."""
        import json
        data = json.dumps({"uids": list(self.processed_uids)})
        # Keep only last 50 to prevent unbounded growth
        if len(self.processed_uids) > 50:
            self.processed_uids = set(list(self.processed_uids)[-50:])
        await self.capability_worker.write_file(
            "protonmail_processed.json", 
            json.dumps({"uids": list(self.processed_uids)})
        )
