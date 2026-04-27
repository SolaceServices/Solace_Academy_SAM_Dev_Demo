"""
Email Tool for SAM Agents

A Python tool that enables agents to send alert emails via a mock email service.
Designed for Course 500: Tooling and Plugins demonstration.

In production, this would be replaced with AWS SES, SendGrid, or SMTP integration.
"""

import requests
from typing import Dict, Any
from solace_agent_mesh.agent.tools.dynamic_tool import DynamicTool
from google.genai import types as adk_types


class EmailTool(DynamicTool):
    """
    Tool for sending alert emails via mock email service.
    
    This tool wraps HTTP calls to a local email service running on port 3000.
    Agents can use this to send notifications when high-priority incidents occur.
    """
    
    def __init__(self, tool_config: Dict[str, Any]):
        """
        Initialize the email tool.

        Args:
            tool_config: Configuration dictionary with 'service_url' and optional 'tool_name' keys
        """
        super().__init__(tool_config)
        self.service_url = tool_config.get('service_url', 'http://localhost:3000').rstrip('/')
        self._tool_name = tool_config.get('tool_name', 'send_alert_email')
    
    @property
    def tool_name(self) -> str:
        """Return the function name that the LLM will call."""
        return self._tool_name
    
    @property
    def tool_description(self) -> str:
        """Return the description of what this tool does."""
        return """Send an alert email for high-priority incidents.

This tool sends email notifications via a mock email service. Use it to alert
administrators when critical incidents are detected.

The email will appear in the mock inbox at http://localhost:3000"""
    
    @property
    def parameters_schema(self) -> adk_types.Schema:
        """Define the parameters this tool accepts."""
        return adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties={
                "recipient": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Email address to send to (e.g., admin@acme.com)"
                ),
                "subject": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Email subject line (e.g., [ALERT] High Priority: Database timeout)"
                ),
                "body": adk_types.Schema(
                    type=adk_types.Type.STRING,
                    description="Email body with incident details. Can include line breaks."
                ),
            },
            required=["recipient", "subject", "body"],
        )
    
    async def _run_async_impl(self, args: dict, tool_context, credential=None) -> dict:
        """
        Internal method called by the framework.
        
        Args:
            args: Dictionary containing recipient, subject, and body
            tool_context: Tool execution context
            credential: Optional credential (not used)
        
        Returns:
            Dictionary with status, messageId, and timestamp (or error)
        """
        recipient = args.get("recipient", "")
        subject = args.get("subject", "")
        body = args.get("body", "")
        
        return await self.run(recipient, subject, body)
    
    async def run(self, recipient: str, subject: str, body: str) -> Dict[str, Any]:
        """
        Send an alert email.
        
        This is the main method that gets called when the agent uses this tool.
        
        Args:
            recipient: Email address to send to
            subject: Email subject line
            body: Email body content
        
        Returns:
            Dictionary with status, messageId, and timestamp (or error)
        """
        # Validate inputs
        if not recipient or not subject or not body:
            return {
                "status": "failed",
                "error": "Missing required fields: recipient, subject, and body are all required"
            }
        
        try:
            # Make HTTP request to email service
            response = requests.post(
                f"{self.service_url}/send-email",
                json={
                    "recipient": recipient,
                    "subject": subject,
                    "body": body
                },
                timeout=5  # 5 second timeout
            )
            
            # Check if request was successful
            response.raise_for_status()
            
            # Return the response from email service
            return response.json()
            
        except requests.exceptions.Timeout:
            return {
                "status": "failed",
                "error": f"Email service timeout: No response from {self.service_url} within 5 seconds"
            }
        
        except requests.exceptions.ConnectionError:
            return {
                "status": "failed",
                "error": f"Email service unavailable: Could not connect to {self.service_url}. Is the service running?"
            }
        
        except requests.exceptions.HTTPError as e:
            return {
                "status": "failed",
                "error": f"Email service error: {e.response.status_code} - {e.response.text}"
            }
        
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Unexpected error sending email: {str(e)}"
            }


# Example usage for testing
if __name__ == "__main__":
    import asyncio
    
    # Create tool instance
    tool = EmailTool(tool_config={"service_url": "http://localhost:3000"})
    
    async def test():
        # Send test email
        print("Sending test email...")
        result = await tool.run(
            recipient="admin@acme.com",
            subject="[TEST] Email Tool Integration",
            body="This is a test email from the EmailTool class.\n\nIf you see this in the inbox, the integration is working!"
        )
        print(f"Result: {result}\n")
        
        if result.get("status") == "sent":
            print(f"✅ Email sent successfully!")
            print(f"   Message ID: {result.get('messageId')}")
            print(f"   Timestamp: {result.get('timestamp')}")
            print(f"\nView the email at: http://localhost:3000")
        else:
            print(f"❌ Email failed to send: {result.get('error')}")
    
    asyncio.run(test())
