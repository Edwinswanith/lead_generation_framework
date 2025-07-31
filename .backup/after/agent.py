from google.adk.agents import LlmAgent, SequentialAgent
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
    - ceo_email: The CEO's business email address
    
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
    
    Return a JSON with:
    {
        "ceo_name": "Full verified name",
        "ceo_email": "Verified business email"
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
    You are a meticulous corporate researcher. Research the company: {company_name}.
    Focus on finding the company's revenue information. Return a JSON with the following fields:
    - company_revenue: The company's revenue
    
    Follow these steps to find accurate information:
    1. First check the company's website, especially About/Team/Contact pages
    2. Search LinkedIn for company profile and CEO/leadership profiles
    3. Check business directories like Crunchbase, ZoomInfo
    4. Look for press releases and news articles
    5. Verify information across multiple sources when possible
    
    For revenue/employees/founding year:
    1. Company about pages
    2. Business registries
    3. LinkedIn company profile
    4. Industry databases
    
    Return null ONLY if you cannot find the information after exhausting all sources.
    Only return the JSON object, no additional text.
    Return a JSON with:
    {
        "company_revenue": "Verified revenue figure"
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
        
    EXAMPLE OUTPUT:
        - output should be in digit number only.
        - Dont include any other text or symbols.
        - Dont include [] or {} or any other symbols.
        - example company_employee_count: 21 to 40 or 41 or 21
        - example company_founding_year: 2012 or 2014
    You MUST exhaust all these sources before returning null.
    
    Return a JSON with:
    {
        "company_employee_count": "Verified employee count",
        "company_founding_year": "Verified founding year"
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
    You are a meticulous ranking agent. Your task is to deeply analyze the company: {company_name} using all gathered information.
    
    You have access to the following information:
    - Document Content: {document_content}
    - Company Employee Count: {company_employee_count}
    - Company Revenue: {company_revenue}
    - Target Industries: {target_industries}
    - Target Company Size: {target_company_size}
    - Target Geography: {target_geography}
    - Client Examples: {client_examples}
    - Service Focus: {service_focus}
    
    Follow this detailed analysis process:
    1. Service Alignment Analysis:
        - Compare service offerings (using 'Service Focus' and 'Document Content')
        - Check technology compatibility
        - Review solution fit
        - Analyze implementation potential
        - Study integration possibilities
        
    2. Market Fit Evaluation:
        - Compare industry focus (using 'Target Industries' and 'Document Content')
        - Check size compatibility (using 'Target Company Size' and 'Company Employee Count')
        - Review geographical match (using 'Target Geography')
        - Analyze growth alignment
        - Study cultural fit
        
    3. Financial Assessment:
        - Analyze revenue data (using 'Company Revenue')
        - Check growth trajectory
        - Review market position
        - Study investment potential
        - Evaluate budget fit
        
    4. Opportunity Analysis:
        - Identify growth areas
        - Check expansion potential
        - Review cross-sell opportunities
        - Analyze service gaps
        - Study partnership potential
        
    5. Risk Evaluation:
        - Check market stability
        - Review competition
        - Analyze industry trends
        - Study economic factors
        - Evaluate implementation risks
        
    You MUST complete all analyses before scoring.
    
    Return a JSON with:
    {
        "ranking": "Score 1-10 based on detailed analysis",
        "reasoning": "Detailed explanation of score with specific evidence"
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