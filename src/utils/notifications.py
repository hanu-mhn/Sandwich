"""
Notification Manager

Handles sending notifications via email, SMS, or other channels
for trade entries, exits, and important events.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional
from datetime import datetime
import requests


class NotificationManager:
    """Manages various notification channels"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize notification manager
        
        Args:
            config: Notification configuration
        """
        self.config = config
        self.enabled = config.get('enabled', False)
        self.logger = logging.getLogger(__name__)
        
        # Email configuration
        self.email_config = config.get('email', {})
        self.email_enabled = self.email_config.get('enabled', False)
        
        # Telegram configuration
        self.telegram_config = config.get('telegram', {})
        self.telegram_enabled = self.telegram_config.get('enabled', False)
    
    def send_entry_notification(self, positions: List, capital_deployed: float) -> None:
        """
        Send notification when strategy enters positions
        
        Args:
            positions: List of Position objects
            capital_deployed: Total capital deployed
        """
        if not self.enabled:
            return
        
        try:
            subject = "🟢 Bank Nifty Strategy - Entry Executed"
            
            message = self._format_entry_message(positions, capital_deployed)
            
            self._send_notification(subject, message)
            
        except Exception as e:
            self.logger.error(f"Failed to send entry notification: {str(e)}")
    
    def send_exit_notification(self, total_pnl: float, capital_deployed: float) -> None:
        """
        Send notification when strategy exits positions
        
        Args:
            total_pnl: Total profit/loss
            capital_deployed: Total capital that was deployed
        """
        if not self.enabled:
            return
        
        try:
            percentage_return = (total_pnl / capital_deployed) * 100 if capital_deployed > 0 else 0
            
            if total_pnl >= 0:
                subject = "🟢 Bank Nifty Strategy - Profitable Exit"
                emoji = "💰"
            else:
                subject = "🔴 Bank Nifty Strategy - Loss Exit"
                emoji = "📉"
            
            message = self._format_exit_message(total_pnl, percentage_return, capital_deployed, emoji)
            
            self._send_notification(subject, message)
            
        except Exception as e:
            self.logger.error(f"Failed to send exit notification: {str(e)}")
    
    def send_risk_alert(self, alert_type: str, message: str) -> None:
        """
        Send risk management alert
        
        Args:
            alert_type: Type of risk alert
            message: Alert message
        """
        if not self.enabled:
            return
        
        try:
            subject = f"⚠️ Risk Alert - {alert_type}"
            
            full_message = f"""
Risk Alert: {alert_type}

{message}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}
Strategy: Bank Nifty Monthly Expiry

Please review your positions immediately.
"""
            
            self._send_notification(subject, full_message)
            
        except Exception as e:
            self.logger.error(f"Failed to send risk alert: {str(e)}")
    
    def send_system_alert(self, alert_type: str, message: str) -> None:
        """
        Send system alert (errors, connectivity issues, etc.)
        
        Args:
            alert_type: Type of system alert
            message: Alert message
        """
        if not self.enabled:
            return
        
        try:
            subject = f"🔧 System Alert - {alert_type}"
            
            full_message = f"""
System Alert: {alert_type}

{message}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}
Strategy: Bank Nifty Monthly Expiry

Please check the system logs for more details.
"""
            
            self._send_notification(subject, full_message)
            
        except Exception as e:
            self.logger.error(f"Failed to send system alert: {str(e)}")
    
    def _format_entry_message(self, positions: List, capital_deployed: float) -> str:
        """Format entry notification message"""
        message = f"""
Bank Nifty Monthly Expiry Strategy - Entry Executed

Entry Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}
Capital Deployed: ₹{capital_deployed:,.2f}
Total Positions: {len(positions)}

Position Details:
"""
        
        for i, position in enumerate(positions, 1):
            action_emoji = "📈" if position.action == "BUY" else "📉"
            message += f"{i}. {action_emoji} {position.action} {position.quantity} lots of {position.instrument} @ ₹{position.price}\n"
        
        message += f"""
Strategy Parameters:
- Profit Target: 10%
- Auto-exit on target achievement

Monitor your positions closely. Good luck! 🚀
"""
        
        return message
    
    def _format_exit_message(self, total_pnl: float, percentage_return: float, 
                           capital_deployed: float, emoji: str) -> str:
        """Format exit notification message"""
        message = f"""
Bank Nifty Monthly Expiry Strategy - Exit Executed {emoji}

Exit Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}

Performance Summary:
- Capital Deployed: ₹{capital_deployed:,.2f}
- Total P&L: ₹{total_pnl:,.2f}
- Return: {percentage_return:.2f}%

All positions have been closed successfully.

Strategy cycle completed! 🎯
"""
        
        return message
    
    def _send_notification(self, subject: str, message: str) -> None:
        """Send notification via all enabled channels"""
        if self.email_enabled:
            self._send_email(subject, message)
        
        if self.telegram_enabled:
            self._send_telegram(message)
    
    def _send_email(self, subject: str, message: str) -> None:
        """
        Send email notification
        
        Args:
            subject: Email subject
            message: Email message
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_config['username']
            msg['Subject'] = subject
            
            # Add recipients
            to_addresses = self.email_config.get('to_addresses', [])
            if isinstance(to_addresses, str):
                to_addresses = [to_addresses]
            
            msg['To'] = ', '.join(to_addresses)
            
            # Add body
            msg.attach(MIMEText(message, 'plain'))
            
            # Send email
            server = smtplib.SMTP(
                self.email_config['smtp_server'], 
                self.email_config['smtp_port']
            )
            server.starttls()
            server.login(
                self.email_config['username'], 
                self.email_config['password']
            )
            
            text = msg.as_string()
            server.sendmail(msg['From'], to_addresses, text)
            server.quit()
            
            self.logger.info(f"Email notification sent: {subject}")
            
        except Exception as e:
            self.logger.error(f"Failed to send email notification: {str(e)}")
    
    def _send_telegram(self, message: str) -> None:
        """
        Send Telegram notification
        
        Args:
            message: Message to send
        """
        try:
            bot_token = self.telegram_config['bot_token']
            chat_id = self.telegram_config['chat_id']
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("Telegram notification sent successfully")
            else:
                self.logger.error(f"Telegram notification failed: {response.text}")
                
        except Exception as e:
            self.logger.error(f"Failed to send Telegram notification: {str(e)}")
    
    def test_notifications(self) -> Dict[str, bool]:
        """
        Test all notification channels
        
        Returns:
            Dict: Results of notification tests
        """
        results = {}
        
        test_subject = "🧪 Test Notification - Bank Nifty Strategy"
        test_message = f"""
This is a test notification from the Bank Nifty Trading Strategy system.

Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}

If you receive this message, notifications are working correctly! ✅
"""
        
        if self.email_enabled:
            try:
                self._send_email(test_subject, test_message)
                results['email'] = True
            except Exception as e:
                self.logger.error(f"Email test failed: {str(e)}")
                results['email'] = False
        
        if self.telegram_enabled:
            try:
                self._send_telegram(test_message)
                results['telegram'] = True
            except Exception as e:
                self.logger.error(f"Telegram test failed: {str(e)}")
                results['telegram'] = False
        
        return results
