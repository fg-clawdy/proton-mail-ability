"""
Background Daemon for ProtonMail Email Monitoring

NOTE: imaplib and smtplib are blocked in OpenHome sandbox.
This demonstrates the architecture - for production, 
either:
1. Platform adds IMAP support, or
2. Use ProtonMail HTTP API via urllib

Architecture:
- Polls every N minutes for new emails
- Notifies on new mail from designated sender  
- Auto-purges emails older than X days (default 31)
"""

import json
from datetime import datetime, timedelta

from src.agent.capability import MatchingCapability
from src.main import AgentWorker
from src.agent.capability_worker import CapabilityWorker


class ProtonMailDaemon(MatchingCapability):
    """Background daemon for ProtonMail monitoring."""
    
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    background_daemon_mode: bool = False
    
    # Configuration
    proton_email: str = ""
    designated_sender: str = ""
    poll_interval_minutes: int = 10
    purge_days: int = 31
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
            proton_email=data.get("proton_email", ""),
            designated_sender=data.get("designated_sender", ""),
            poll_interval_minutes=data.get("poll_interval_minutes", 10),
            purge_days=data.get("purge_days", 31),
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
            f"ProtonMail daemon started. Poll: {self.poll_interval_minutes}min, "
            f"Purge: {self.purge_days} days"
        )
        
        # Load state
        await self._load_state()
        
        try:
            while True:
                # Check for new mail (would use IMAP in production)
                await self._check_mail()
                
                # Purge old emails
                await self._purge_old_emails()
                
                # Save state
                await self._save_state()
                
                await self.worker.session_tasks.sleep(self.poll_interval_minutes * 60)
                
        except Exception as e:
            self.worker.editor_logging_handler.error(f"Daemon error: {e}")

    async def _check_mail(self):
        """Check for new emails from designated sender."""
        if not self.designated_sender:
            return
        
        # NOTE: In production, this would use IMAP:
        # import imaplib
        # mail = imaplib.IMAP4_SSL('imap.protonmail.com')
        # mail.login(self.proton_email, password)
        # ...
        
        # For now, log the intended behavior
        self.worker.editor_logging_handler.info(
            f"Would check IMAP for emails from {self.designated_sender}"
        )
        
        # Simulated check - in production would fetch real emails
        # If new email found:
        #   await self.capability_worker.send_interrupt_signal()
        #   if self.mail_notifications:
        #       await self.capability_worker.speak("You've got mail!")
        #   await self._process_email(email_data)

    async def _purge_old_emails(self):
        """Purge emails older than purge_days."""
        self.worker.editor_logging_handler.info(
            f"Running email purge (older than {self.purge_days} days)"
        )
        
        # NOTE: In production, this would use IMAP to delete:
        # import imaplib
        # mail = imaplib.IMAP4_SSL('imap.protonmail.com')
        # mail.login(...)
        # mail.select('INBOX')
        # # Search and delete emails older than purge_days
        # ...
        
        # Calculate cutoff date
        cutoff = datetime.now() - timedelta(days=self.purge_days)
        self.worker.editor_logging_handler.info(
            f"Would purge emails before {cutoff.strftime('%Y-%m-%d')}"
        )

    async def _process_email(self, email_data: dict):
        """Process email from designated sender - parse as command."""
        email_body = email_data.get('body', '')[:1000]
        
        await self.capability_worker.speak("Processing email command...")
        
        # Parse body as voice command
        action_prompt = (
            f"Email command from {email_data['from']}:\n"
            f"Subject: {email_data['subject']}\n"
            f"Body: {email_body}\n\n"
            f"Execute this command."
        )
        
        response = self.capability_worker.text_to_text_response(action_prompt)
        
        await self.capability_worker.speak(f"Done. {response}")
        
        # Auto-reply (would use SMTP in production)
        # import smtplib
        # server = smtplib.SMTP('smtp.protonmail.com', 587)
        # ...
        
        self.worker.editor_logging_handler.info(f"Would send auto-reply to {email_data['from']}")

    async def _load_state(self):
        """Load processed email UIDs."""
        exists = await self.capability_worker.check_if_file_exists("protonmail_state.json")
        if exists:
            content = await self.capability_worker.read_file("protonmail_state.json")
            if content:
                try:
                    data = json.loads(content)
                    self.processed_uids = set(data.get("processed", []))
                except:
                    pass

    async def _save_state(self):
        """Save processed email UIDs."""
        import json
        # Keep last 50
        if len(self.processed_uids) > 50:
            self.processed_uids = set(list(self.processed_uids)[-50:])
        
        data = json.dumps({"processed": list(self.processed_uids)})
        await self.capability_worker.write_file("protonmail_state.json", data)
