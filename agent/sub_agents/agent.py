from google.adk.agents import LlmAgent, SequentialAgent, Agent
from google.adk.tools import google_search


GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_MODEL_2 = "gemini-1.5-pro"
GEMINI_MODEL_3 = "gemini-2.0-flash-lite"



def create_sequential_agent() -> SequentialAgent:
    """Creates and returns a new instance of the sequential agent."""
    ceo_researcher = LlmAgent(
        name="CEOResearcher",
        model=GEMINI_MODEL,
        tools=[google_search],
        instruction="""
    You are a meticulous corporate researcher. Research the company: {company_name}.
    Focus on finding the CEO's information. Return a JSON with the following fields:
    - ceo_name: The full name of the current CEO/President
    - ceo_email: The CEO's valid business email address
    
    Follow these steps to find accurate information:
    1. First check the company's website, especially About/Team/Contact pages
    2. Search LinkedIn for company profile and CEO/leadership profiles
    3. Check business directories like Crunchbase, ZoomInfo
    4. Look for press releases and news articles
    5. Verify information across multiple sources when possible
    
    For email, specifically target the CEO's direct email:
    1. Company leadership/about pages with executive contact details
    2. CEO's professional LinkedIn profile
    3. Executive directories and business databases
    4. Press releases or interviews mentioning CEO contact
    
    IMPORTANT: Only find the CEO's personal business email. 
    Do NOT include:
    - General sales emails (sales@, info@, contact@)
    - General customer service emails
    - Marketing or support emails
    - Anyone else's email except the CEO's
    
    Return null ONLY if you cannot find the CEO's specific email after exhausting all sources.
    
    Return a JSON with:
    {
        "ceo_name": "Full verified name",
        "ceo_email": "CEO's verified business email only"
    }
    
    Only return the JSON object, no other text.
    """,
        output_key="ceo_info"
    )

    revenue_researcher = LlmAgent(
        name="RevenueResearcher", 
        model=GEMINI_MODEL,
        tools=[google_search],
        instruction="""
    You are a meticulous corporate researcher. Your task is to deeply research the company: {company_name} and find accurate revenue information.
    
    Follow this comprehensive research process:
    1. Financial Documents & Reports:
        - Search for annual reports and SEC filings
        - Check quarterly earnings reports
        - Review investor relations pages
        - Find financial statements and disclosures
        
    2. Business Databases & Registries:
        - Search Crunchbase for funding and revenue data
        - Check D&B (Dun & Bradstreet) company records
        - Review ZoomInfo financial information
        - Search Bloomberg company profiles
        
    3. Company Website Deep Analysis:
        - Thoroughly check About/Company pages
        - Review investor relations sections
        - Search press releases for financial announcements
        - Check company milestone achievements
        
    4. Professional Networks & Industry Sources:
        - Analyze LinkedIn company insights
        - Search industry reports mentioning the company
        - Check trade publications and industry databases
        - Review competitor analysis reports
        
    5. News & Media Research:
        - Search financial news articles
        - Check business journal coverage
        - Review acquisition/funding announcements
        - Find interview mentions of company size/revenue
        
    6. Alternative Revenue Indicators:
        - Research funding rounds and valuations
        - Check contract announcements and deals
        - Search for revenue growth mentions
        - Find market share and industry positioning data
        
    IMPORTANT GUIDELINES:
    - Prioritize recent data (within last 2 years)
    - Cross-verify information from multiple sources
    - Look for exact figures when possible
    - If exact revenue unavailable, find revenue ranges
    - Note the year/period for revenue figures
    
    EXAMPLE OUTPUT FORMAT:
    - For exact figures: "$5200000" or "€15000000"
    - For ranges: "$1000000-$5000000" or "$10000000-$50000000"
    - For estimates: "$25000000"
    
    You MUST exhaust all these sources before returning null.
    Return only the revenue amount with currency symbol, no additional text.
    
    Return a JSON with:
    {
        "company_revenue": "Revenue amount with currency symbol only"
    }
    
    Only return the JSON object, no other text.
    """,
        output_key="revenue_info"
    )

    company_stats_researcher = LlmAgent(
        name="CompanyStatsResearcher",
        model=GEMINI_MODEL,
        tools=[google_search],
        instruction="""
    You are a meticulous corporate researcher. Your task is to deeply research the company: {company_name} and find accurate employee count and founding information.
    
    Follow this detailed research process:
    1. Company Website Research:
        - Search About/History pages thoroughly
        - Check Career/Jobs sections
        - Review company timeline content
        - Find foundation story content
        
    2. Business Registries:
        - Search incorporation records
        - Check business licenses
        - Review legal filings
        - Find registration dates
        
    3. Professional Networks:
        - Analyze LinkedIn employee count
        - Check Glassdoor company size
        - Review Indeed company pages
        - Search employee reviews
        
    4. Business Databases:
        - Search Crunchbase history
        - Check D&B company records
        - Review Bloomberg profiles
        - Find ZoomInfo data
        
    5. Historical Sources:
        - Search news archives
        - Check company milestones
        - Review founder interviews
        - Find anniversary announcements
        
    IMPORTANT OUTPUT REQUIREMENTS:
    - Return only integer numbers for both fields
    - No text, symbols, ranges, or explanations
    - For employee count: return exact number (e.g. 25, 150)
    - For founding year: return 4-digit year (e.g. 2012, 2014)
    - If multiple companies exist with same name, use additional context like location or industry to identify the correct one
    - Return null only if information cannot be found after exhaustive search
    
    Return a JSON with:
    {
        "company_employee_count": integer_only,
        "company_founding_year": integer_only
    }
    
    Only return the JSON object, no other text.
    """,
        output_key="company_stats_info"
    )

    client_target_agent = LlmAgent(
        name="ClientTargetAgent",
        model=GEMINI_MODEL,
        tools=[google_search],
        include_contents='none',
        instruction="""
    You are a meticulous corporate researcher. Research the company: {company_name}.
    Focus on finding the company's employee count and founding year. Return a JSON with the following fields:
    - company_employee_count: The company's employee count
    - company_founding_year: The company's founding year
    
    Follow these steps to find accurate information:
    1. First check the company's website, especially About/Team/Contact pages
    2. Search LinkedIn for company profile and CEO/leadership profiles
    3. Check business directories like Crunchbase, ZoomInfo
    4. Look for press releases and news articles
    5. Verify information across multiple sources when possible
    
    For employee count and founding year:
    1. Company about pages
    2. Business registries
    3. LinkedIn company profile
    4. Industry databases
    
    Return null ONLY if you cannot find the information after exhausting all sources.
    Only return the JSON object, no additional text.
    
    Return a JSON with:
    {
        "target_industries": ["Verified industries"],
        "target_company_size": ["Verified size segments"],
        "target_geography": ["Verified regions"],
        "client_examples": [{"name": "Verified name", "website": "Verified URL"}],
        "service_focus": ["Verified services"]
    }
    
    Only return the JSON object, no other text.
    """,
        output_key="client_target_info"
    )

    ranking_agent = LlmAgent(
        name="RankingAgent",
        model=GEMINI_MODEL_2,
        tools=[google_search],
        include_contents='none',
        instruction="""
    You are a meticulous ranking agent. Your task is to analyze potential collaboration between two companies:
    1. Your company (described in {document_content})
    2. The target company: {company_name}

    You have access to the following information about the target company:
    - Company Employee Count: {company_employee_count}
    - Company Revenue: {company_revenue} 
    - Target Industries: {target_industries}
    - Target Company Size: {target_company_size}
    - Target Geography: {target_geography}
    - Client Examples: {client_examples}
    - Service Focus: {service_focus}

    Follow this collaboration analysis process:
    1. Business Alignment:
        - Compare core business focus and services
        - Identify complementary offerings
        - Evaluate market overlap
        - Assess potential synergies
        
    2. Strategic Fit:
        - Compare target markets and industries
        - Evaluate geographical presence
        - Check company sizes and growth stages
        - Assess cultural alignment
        
    3. Collaboration Potential:
        - Identify joint opportunities
        - Evaluate resource compatibility
        - Assess technical integration feasibility
        - Consider knowledge sharing potential
        
    4. Risk Assessment:
        - Evaluate competitive conflicts
        - Check geographical challenges
        - Assess operational compatibility
        - Consider regulatory factors   

    Based on comparing both companies, provide:
    {
        "ranking": "Score 1-10 based on collaboration potential",
        "reasoning": "Detailed explanation of the collaboration score, highlighting key synergies and potential challenges"
    }

    Only return the JSON object, no other text.
    """,
        output_key="ranking"
    )

    return SequentialAgent(
        name="InfoProcessing",
        sub_agents=[
            ceo_researcher,
            revenue_researcher,
            company_stats_researcher,
            client_target_agent,
            ranking_agent
        ]
    )

# Add a function to create an email sequence agent
def create_email_sequence_agent() -> SequentialAgent:
    """Creates and returns a new instance of the email sequence agent."""
    email_content_agent = LlmAgent(
            name="EmailContentGenerator",
            model=GEMINI_MODEL_2,  # Using the more capable model for better content generation
            instruction="""
        You are an expert email content writer specializing in B2B communication. Your task is to analyze the company data and create highly personalized email content.

        Use the following company information from the session state:
        - Company Name: {company_name}
        - CEO Name: {ceo_name}
        - Service Focus: {service_focus}
        - Target Industries: {target_industries}
        - Client Examples: {client_examples}
        - Email: {email}
        
        Follow these guidelines to create compelling email content:
        1. Personalization:
            - Use CEO's name naturally in greeting (if available, otherwise use "Hi")
            - Reference company's specific services/focus
            - Mention relevant industry expertise
            
        2. Value Proposition:
            - Connect our AI solutions to their service focus
            - Highlight relevant case studies/success stories
            - Emphasize efficiency gains and cost savings
            
        3. Tone and Style:
            - Professional yet conversational
            - Clear and concise
            - Solution-focused
            - Avoid generic sales language
            
        4. Call to Action:
            - Suggest a brief call/meeting
            - Make it easy to respond
            - Be specific but not pushy

        Return a JSON with:
        {
            "subject": "Clear, personalized subject line",
            "body": "Full HTML email body with proper formatting"
        }

        The body should include:
        - Professional greeting
        - 2-3 concise paragraphs
        - Clear value proposition
        - Specific call to action
        - Professional signature block with:
        * {sender_name}
        * {sender_role}
        * Bizzzup
        
        IMPORTANT: Always use the actual sender_name and sender_role from the session state in the signature, not placeholders.
        
        Only return the JSON object, no other text.
        """,
            output_key="email_content"
    )
    
    return SequentialAgent(
        name="EmailSequenceAgent",
        sub_agents=[email_content_agent]
    )

def create_follow_up_agent() -> SequentialAgent:
    
    follow_up_email_agent = LlmAgent(
        name="FollowUpAgent",
        model=GEMINI_MODEL_2,
        instruction="""
        You are a follow-up email specialist. Create a professional follow-up email for company: {company_name}.
        
        Based on the provided context:
        - CEO Name: {ceo_name}
        - Company Information: {company_info}
        - Previous email subject: {previous_subject}
        - Sender name: {sender_name}
        - Sender role: {sender_role}
        
        Create a compelling follow-up email that:
        
        1. References the previous communication subtly
        2. Provides additional value or insight
        3. Creates urgency without being pushy
        4. Offers multiple ways to engage
        
        Follow these guidelines:
        1. Personalization:
            - Use CEO's name if available
            - Reference specific company details
            - Acknowledge they may be busy
            
        2. Value Addition:
            - Share a relevant insight or case study
            - Mention industry trends relevant to their business
            - Offer a free resource or consultation
            
        3. Tone and Style:
            - Respectful and understanding
            - Brief and to the point
            - Professional but warm
            - Solution-focused
            
        4. Call to Action:
            - Offer multiple engagement options (call, email, demo)
            - Suggest specific time frames
            - Make it easy to decline if not interested

        Return a JSON with:
        {
            "subject": "Compelling follow-up subject line",
            "body": "Full HTML email body with proper formatting"
        }

        The body should include:
        - Polite acknowledgment of previous email
        - 2-3 short paragraphs with value-add content
        - Clear but flexible call to action
        - Professional signature with sender details
        - Option to unsubscribe/decline
        
        IMPORTANT: Use actual sender_name and sender_role in signature, not placeholders.
        
        Only return the JSON object, no other text.
        """,
        output_key="follow_up_email_content"
    )

    return SequentialAgent(
        name="FollowUpAgent",
        sub_agents=[follow_up_email_agent]
    )