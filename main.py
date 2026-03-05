"""
ProtonMail Monitor Ability for OpenHome
Background email monitoring with voice notifications

Note: IMAP/SMTP imports are blocked in OpenHome sandbox.
This ability demonstrates the background daemon architecture.
For production, IMAP would need to be allowed or use HTTP API.

Features:
- Background daemon for email polling (see background.py)
- Auto-purge emails older than X days (configurable, default 31)
- Voice notifications for new mail from designated sender
"""

import json
import os

from src.agent.capability import MatchingCapability
from src.main import AgentWorker
from src.agent.capability_worker import CapabilityWorker


class ProtonMailMonitor(MatchingCapability):
    """Monitor ProtonMail inbox for new messages."""
    
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    
    # Configuration
    proton_email: str = ""
    designated_sender: str = ""
    purge_days: int = 31
    mail_notifications: bool = True
    
    # Do not change following tag of register capability
    #{{register capability}}

    @classmethod
    def register_capability(cls) -> "ProtonMailMonitor":
        with open(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        ) as file:
            data = json.load(file)
        return cls(
            unique_name=data["unique_name"],
            matching_hotwords=data["matching_hotwords"],
            proton_email=data.get("proton_email", ""),
            designated_sender=data.get("designated_sender", ""),
            purge_days=data.get("purge_days", 31),
            mail_notifications=data.get("mail_notifications", True),
        )

    def call(self, worker: AgentWorker):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self.worker)
        self.worker.session_tasks.create(self.run())

    async def run(self):
        try:
            await self._run_monitor()
        except Exception as e:
            self.worker.editor_logging_handler.error(f"ProtonMail monitor error: {e}")
            await self.capability_worker.speak("Error with mail monitor.")
        finally:
            self.capability_worker.resume_normal_flow()

    async def _run_monitor(self):
        """Main ability logic - check status and explain background daemon."""
        
        await self.capability_worker.speak(
            "ProtonMail monitor ready. "
            f"Background daemon will check for mail every 10 minutes. "
            f"Emails older than {self.purge_days} days will be auto-purged. "
            f"Notifications are {'on' if self.mail_notifications else 'off'}."
        )
        
        if self.designated_sender:
            await self.capability_worker.speak(
                f"You'll be notified about mail from {self.designated_sender}."
            )
        else:
            await self.capability_worker.speak(
                "No designated sender set. All new mail will trigger notifications."
            )

    # NOTE: Actual IMAP functionality is in background.py
    # It requires imaplib which is blocked in the sandbox
    # For production deployment, this would need platform support
