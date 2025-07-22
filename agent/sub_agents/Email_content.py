from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field
from typing import Dict
from google.adk.tools.agent_tool import AgentTool 


GEMINI_MODEL_4 = "gemini-2.5-flash"

class EmailContent(BaseModel):
    subject: str = Field(
        description="The subject line for the collaboration proposal email"
    )
    body: str = Field(
        description="Email body containing partnership proposal content"
    )

email_content_agent = LlmAgent(
    name="email_agent",
    model=GEMINI_MODEL_4,
    description="Creates professional collaboration proposal emails from partnership analysis",
    instruction="""
You are a business writer. Based on the provided collaboration proposal: {collaboration_proposal},
write a professional and compelling email body.

The email should be structured with the following sections, using the information from the proposal:

### Company Alignment
Use the `company_alignment.overview` to explain how our AI solutions can be integrated into their existing operations to create value.

### Market Edge
Use the `market_edge.performance_improvement` to articulate the competitive advantage they would gain. Focus on performance improvements and potential ROI.

### Top Benefits
Use `top_benefits.advantages` to list the most compelling advantages of the partnership in a clear, concise format.

### Bizzzup Walkthrough
Use `bizzzup_walkthrough.overview` to provide a brief, impactful overview of Bizzzup's relevant work.
Make sure to include these links:
- Bizzzup Website: `https://labs.bizzzup.com/`
- Upwork Portfolio: `https://www.upwork.com/nx/find-work/`

Keep the tone client-focused and benefits-oriented.
""",
    output_schema=EmailContent,
    output_key="email",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True
    
)
