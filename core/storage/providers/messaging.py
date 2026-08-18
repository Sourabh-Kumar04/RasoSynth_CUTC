"""
Messaging & Notification Provider Implementations

Telegram, Discord, Slack, Email, Webhook support.
"""

import asyncio
import json
import smtplib
import aiohttp
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from datetime import datetime

from core.storage.base import (
    StorageProvider,
    StorageConfig,
    StorageResult,
    StorageMetadata,
    StorageProviderType,
)


class TelegramProvider(StorageProvider):
    """Telegram Bot API delivery provider."""

    provider_type = StorageProviderType.TELEGRAM

    async def initialize(self) -> None:
        """Initialize Telegram bot."""
        self._bot_token = self.config.credentials.get("bot_token", "")
        self._chat_id = self.config.metadata.get("chat_id", "")

    async def send_message(
        self,
        message: str,
        chat_id: Optional[str] = None
    ) -> StorageResult:
        """Send Telegram message."""
        start = datetime.utcnow()

        try:
            if not self._bot_token:
                await self.initialize()

            chat_id = chat_id or self._chat_id
            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }) as resp:
                    result = await resp.json()

                    if result.get("ok"):
                        duration = (datetime.utcnow() - start).total_seconds() * 1000
                        return StorageResult(
                            success=True,
                            location=f"tg://{chat_id}",
                            duration_ms=duration,
                        )

            raise Exception("Telegram API error")

        except Exception as e:
            return StorageResult(success=False, location="telegram", errors=[str(e)])

    async def send_file(
        self,
        file_path: str,
        caption: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> StorageResult:
        """Send file via Telegram."""
        start = datetime.utcnow()

        try:
            if not self._bot_token:
                await self.initialize()

            chat_id = chat_id or self._chat_id

            url = f"https://api.telegram.org/bot{self._bot_token}/sendDocument"

            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('chat_id', chat_id)
                form.add_field('document', f, filename=file_path.split('/')[-1])
                if caption:
                    form.add_field('caption', caption)

                async with aiohttp.ClientSession() as session:
                    async with session.post(url, data=form) as resp:
                        result = await resp.json()

                        if result.get("ok"):
                            duration = (datetime.utcnow() - start).total_seconds() * 1000
                            return StorageResult(
                                success=True,
                                location=f"tg://{chat_id}/{result['result']['document']['file_id']}",
                                duration_ms=duration,
                            )

            raise Exception("Telegram upload failed")

        except Exception as e:
            return StorageResult(success=False, location=file_path, errors=[str(e)])

    async def send_link(
        self,
        url: str,
        text: str = "Dataset ready",
        chat_id: Optional[str] = None
    ) -> StorageResult:
        """Send download link via Telegram."""
        message = f"📊 *Dataset Ready*\n\n{text}\n\n🔗 [Download]({url})"
        return await self.send_message(message, chat_id)

    async def upload(
        self,
        data: bytes,
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload via Telegram (for small files)."""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            temp_path = f.name

        return await self.send_file(temp_path, metadata.get("caption") if metadata else None)


class DiscordProvider(StorageProvider):
    """Discord webhook delivery provider."""

    provider_type = StorageProviderType.DISCORD

    async def initialize(self) -> None:
        """Initialize Discord webhook."""
        self._webhook_url = self.config.credentials.get("webhook_url", "")

    async def send_embed(
        self,
        title: str,
        description: str,
        url: Optional[str] = None,
        color: int = 0x3498db
    ) -> StorageResult:
        """Send Discord embed message."""
        start = datetime.utcnow()

        try:
            if not self._webhook_url:
                await self.initialize()

            payload = {
                "embeds": [{
                    "title": title,
                    "description": description,
                    "color": color,
                    "url": url,
                }]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self._webhook_url, json=payload) as resp:
                    if resp.status == 204:
                        duration = (datetime.utcnow() - start).total_seconds() * 1000
                        return StorageResult(
                            success=True,
                            location="discord://webhook",
                            duration_ms=duration,
                        )

            raise Exception("Discord webhook failed")

        except Exception as e:
            return StorageResult(success=False, location="discord", errors=[str(e)])

    async def send_file(
        self,
        file_path: str,
        message: str = "Dataset ready"
    ) -> StorageResult:
        """Send file via Discord."""
        start = datetime.utcnow()

        try:
            if not self._webhook_url:
                await self.initialize()

            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('file', f, filename=file_path.split('/')[-1])
                form.add_field('content', message)

                async with aiohttp.ClientSession() as session:
                    async with session.post(self._webhook_url, data=form) as resp:
                        if resp.status == 200:
                            duration = (datetime.utcnow() - start).total_seconds() * 1000
                            return StorageResult(
                                success=True,
                                location="discord://webhook",
                                duration_ms=duration,
                            )

            raise Exception("Discord file upload failed")

        except Exception as e:
            return StorageResult(success=False, location=file_path, errors=[str(e)])

    async def send_link(
        self,
        url: str,
        title: str = "Dataset Ready",
        description: str = "Your dataset is ready for download"
    ) -> StorageResult:
        """Send download link via Discord."""
        return await self.send_embed(
            title=title,
            description=f"{description}\n\n🔗 [Download]({url})",
            url=url
        )

    async def upload(
        self,
        data: bytes,
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload via Discord."""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            temp_path = f.name

        return await self.send_file(temp_path, metadata.get("message") if metadata else None)


class SlackProvider(StorageProvider):
    """Slack webhook delivery provider."""

    provider_type = StorageProviderType.SLACK

    async def initialize(self) -> None:
        """Initialize Slack webhook."""
        self._webhook_url = self.config.credentials.get("webhook_url", "")
        self._channel = self.config.metadata.get("channel", "")

    async def send_message(
        self,
        text: str,
        blocks: Optional[list] = None
    ) -> StorageResult:
        """Send Slack message."""
        start = datetime.utcnow()

        try:
            if not self._webhook_url:
                await self.initialize()

            payload = {"text": text}
            if blocks:
                payload["blocks"] = blocks

            async with aiohttp.ClientSession() as session:
                async with session.post(self._webhook_url, json=payload) as resp:
                    if resp.status == 200:
                        duration = (datetime.utcnow() - start).total_seconds() * 1000
                        return StorageResult(
                            success=True,
                            location=f"slack://{self._channel}",
                            duration_ms=duration,
                        )

            raise Exception("Slack webhook failed")

        except Exception as e:
            return StorageResult(success=False, location="slack", errors=[str(e)])

    async def send_link(
        self,
        url: str,
        title: str = "Dataset Ready",
        file_size: Optional[str] = None
    ) -> StorageResult:
        """Send download link via Slack."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 Dataset Ready"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*\n\nSize: {file_size or 'N/A'}\n\n<{url}|Download Dataset>"
                }
            }
        ]

        return await self.send_message("Dataset ready for download", blocks=blocks)

    async def upload(
        self,
        data: bytes,
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload via Slack."""
        return await self.send_message(metadata.get("message") if metadata else "Dataset uploaded")


class EmailProvider(StorageProvider):
    """Email delivery provider."""

    provider_type = StorageProviderType.EMAIL

    async def initialize(self) -> None:
        """Initialize email settings."""
        self._smtp_host = self.config.credentials.get("smtp_host", "smtp.gmail.com")
        self._smtp_port = self.config.credentials.get("smtp_port", 587)
        self._smtp_user = self.config.credentials.get("smtp_user", "")
        self._smtp_password = self.config.credentials.get("smtp_password", "")
        self._from_email = self.config.metadata.get("from_email", self._smtp_user)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachments: Optional[list] = None
    ) -> StorageResult:
        """Send email."""
        start = datetime.utcnow()

        try:
            if not self._smtp_user:
                await self.initialize()

            msg = MIMEMultipart()
            msg['From'] = self._from_email
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html'))

            # Add attachments
            if attachments:
                for filepath in attachments:
                    import base64
                    with open(filepath, 'rb') as f:
                        part = MIMEText(base64.b64encode(f.read()).decode(), 'base64')
                        part.add_header('Content-Disposition', f'attachment; filename={filepath.split("/")[-1]}')
                        msg.attach(part)

            # Send
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.starttls()
                server.login(self._smtp_user, self._smtp_password)
                server.send_message(msg)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"mailto://{to_email}",
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=f"mailto:{to_email}", errors=[str(e)])

    async def send_link_email(
        self,
        to_email: str,
        dataset_name: str,
        download_url: str,
        file_size: str,
        expiration: str
    ) -> StorageResult:
        """Send download link via email."""
        subject = f"📊 Dataset Ready: {dataset_name}"
        body = f"""
        <html>
        <body>
            <h2>Your dataset is ready!</h2>
            <p><strong>Dataset:</strong> {dataset_name}</p>
            <p><strong>Size:</strong> {file_size}</p>
            <p><strong>Expires:</strong> {expiration}</p>
            <p><a href="{download_url}">Click here to download</a></p>
            <hr>
            <p><small>RasoSynthTune</small></p>
        </body>
        </html>
        """

        return await self.send_email(to_email, subject, body)

    async def upload(
        self,
        data: bytes,
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload via email (as attachment)."""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            temp_path = f.name

        return await self.send_email(
            metadata.get("to_email") if metadata else "",
            metadata.get("subject") if metadata else "Dataset",
            metadata.get("body") if metadata else "Your dataset",
            attachments=[temp_path]
        )


class WebhookProvider(StorageProvider):
    """Generic webhook delivery provider."""

    provider_type = StorageProviderType.WEBHOOK

    async def initialize(self) -> None:
        """Initialize webhook settings."""
        self._default_url = self.config.credentials.get("webhook_url", "")

    async def send(
        self,
        payload: dict,
        webhook_url: Optional[str] = None
    ) -> StorageResult:
        """Send webhook payload."""
        start = datetime.utcnow()

        try:
            url = webhook_url or self._default_url

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status < 400:
                        duration = (datetime.utcnow() - start).total_seconds() * 1000
                        return StorageResult(
                            success=True,
                            location=url,
                            duration_ms=duration,
                        )

            raise Exception(f"Webhook failed with status {resp.status}")

        except Exception as e:
            return StorageResult(success=False, location=url, errors=[str(e)])

    async def send_delivery_notification(
        self,
        webhook_url: Optional[str],
        dataset_id: str,
        status: str,
        download_url: Optional[str] = None,
        error: Optional[str] = None
    ) -> StorageResult:
        """Send delivery notification webhook."""
        payload = {
            "event": "dataset_delivery",
            "dataset_id": dataset_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if download_url:
            payload["download_url"] = download_url
        if error:
            payload["error"] = error

        return await self.send(payload, webhook_url)

    async def upload(
        self,
        data: bytes,
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload via webhook."""
        payload = {
            "dataset_id": destination,
            "data": data.decode('utf-8', errors='ignore')[:1000] if isinstance(data, bytes) else str(data)[:1000],
            "metadata": metadata or {}
        }

        return await self.send(payload)