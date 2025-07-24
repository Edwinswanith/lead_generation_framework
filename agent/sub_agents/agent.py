from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import google_search


GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_MODEL_2 = "gemini-1.5-pro"
GEMINI_MODEL_3 = "gemini-2.0-flash-lite"


def create_sequential_agent() -> SequentialAgent:
    """Creates and returns a new instance of the sequential agent."""
    company_researcher = LlmAgent(
        name="CompanyResearcher",
        model=GEMINI_MODEL,
        tools=[google_search],
        instruction="""
    You are a meticulous corporate researcher. Research the company: {company_name} (website: {website}).
    Focus on finding the CEO's information. Return a JSON with the following fields:
    - ceo_name: The full name of the current CEO/President
    - ceo_email: The CEO's business email address
    - company_revenue: The company's revenue
    - company_employee_count: The company's employee count
    - company_founding_year: The company's founding year
    
    Follow these steps to find accurate information:
    1. First check the company's website, especially About/Team/Contact pages
    2. Search LinkedIn for company profile and CEO/leadership profiles
    3. Check business directories like Crunchbase, ZoomInfo
    4. Look for press releases and news articles
    5. Verify information across multiple sources when possible
    
    For email, try:
    1. Company contact/about pages
    2. Email patterns like firstname@company.com
    3. Professional networks and directories
    
    For revenue/employees/founding year:
    1. Company about pages
    2. Business registries
    3. LinkedIn company profile
    4. Industry databases
    
    Return null ONLY if you cannot find the information after exhausting all sources.
    Only return the JSON object, no additional text.
""",
        output_key="company_info"
    )

    client_target_agent = LlmAgent(
        name="ClientTargetAgent",
        model=GEMINI_MODEL,
        tools=[google_search],
        include_contents='none',
        instruction="""
    You are a meticulous corporate researcher. Research the company: {company_name} (website: {website}).
        Your task is to analyze their target market and service offerings.

        First, visit their website and thoroughly examine their:
        - Homepage
        - About/Company page  
        - Services/Solutions pages
        - Case Studies/Portfolio
        - Client Testimonials

        Then use the search tool to find additional information from:
        - Press releases
        - News articles
        - LinkedIn company page
        - Industry reports

        Return a JSON with these fields:
        - target_industries: Array of specific industries they serve (e.g. ["Healthcare", "Finance", "Retail"])
        - target_company_size: Array of company sizes they target (e.g. ["SMB", "Mid-Market", "Enterprise"]) 
        - target_geography: Array of regions they operate in (e.g. ["North America", "Europe"])
        - client_examples: Array of objects containing client details, each with:
            - name: Client company name (must be a real, verifiable company)
            - website: Client company website URL (must be active and accessible)
        - service_focus: Array of their main service offerings/solutions

        Only include information you find with high confidence. Use null for any fields where you cannot find reliable data.

        For client examples:
        1. Only include real, well-known companies that you can verify
        2. Test each website URL before including it to ensure it's accessible
        3. Use the company's main domain (e.g. microsoft.com) rather than subdomains
        4. Limit to 2-3 high-confidence examples
        5. Double check that both company name and website match and are correct

        Format the response as clean, properly formatted JSON. Example client_examples format:
        {
            "client_examples": [
                {"name": "Microsoft", "website": "https://www.microsoft.com"},
                {"name": "IBM", "website": "https://www.ibm.com"}
            ]
        }
    Only return the JSON object, no additional text.
    """,
        output_key="client_target_info"
    )

    ranking_agent = LlmAgent(
        name="RankingAgent",
        model=GEMINI_MODEL_2,
        tools=[google_search],
        include_contents='none',
        instruction="""
    You are a ranking agent that evaluates potential business opportunities between companies.

    Analyze the following information:
    - Target company details: {company_info}
    - Target company's market focus: {client_target_info} 
    - Our company's profile: {document_content} 

    Evaluate and rank the opportunity from 1-10 based on these criteria:
    - Service Alignment (0-2 points): How well our services could address their needs
    - Market Fit (0-2 points): How well our AI solutions could enhance their core business activities (e.g. if they specialize in marketing, evaluate opportunities to improve their marketing processes with AI)
    - Company Revenue (0-2 points): Evaluate their revenue potential and financial fit
    - Size Compatibility (0-2 points): Whether their size aligns with our ideal client profile
    - Growth Potential (0-2 points): Opportunities for expanding services/relationship

    For each criterion, consider:
    1. Our company's capabilities and focus areas from {document_content}
    2. The target company's needs and characteristics
    3. Potential synergies and complementary strengths

    Return a JSON with this format:
    {
        "ranking": 8, // Integer between 1-10 representing total score
        "reasoning": "Summary of why the total score was given, highlighting key strengths and any concerns"
    }

    Only return the JSON object, no additional text.
    """,
        output_key="ranking"
    )

    collaboration_agent = LlmAgent(
        name="CollaborationAgent",
        model=GEMINI_MODEL_3,
        tools=[google_search],
        include_contents='none',
        instruction="""
    You are a business collaboration strategist that analyzes partnership opportunities.

    Your purpose is to evaluate potential collaborations by analyzing:
    - Target company details: {company_info}
    - Target company's market focus: {client_target_info}
    - Our company profile: {document_content}

    Craft a client-focused collaboration proposal.

    Return a JSON with this format:
    {
        "company_alignment": {
            "overview": "Explain how our AI workflows can integrate into their operations to add value."
        },
        "market_edge": {
            "performance_improvement": "Focus on how AI and automation can improve their business performance, including potential ROI."
        },
        "top_benefits": {
            "advantages": ["List the key advantages for them in partnering with us."]
        },
        "bizzzup_walkthrough": {
            "overview": "Provide a brief and impactful overview of our relevant work, including links to our website and portfolio."
        }
    }

    Only return the JSON object, no additional text.
    """,
        output_key="collaboration_proposal"
    )

    return SequentialAgent(
        name="InfoProcessing",
        sub_agents=[
            company_researcher,
            client_target_agent,
            ranking_agent,
            collaboration_agent
        ]
    )