import json
import os
import tiktoken
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from langchain_openai import ChatOpenAI
from google.cloud import aiplatform

# from crewai import Crew
# from crewai.task import Task, TaskOutput
from .pricing import PRICING_DATA

# Get the absolute path to the monitoring directory
MONITORING_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(MONITORING_DIR, "crew_log.json")

def count_tokens(string: str, model_name: str = "gpt-4") -> int:
    """Returns the number of tokens in a text string."""
    try:
        # Handle Google's model names, which may not be in tiktoken
        if model_name.startswith("gemini"):
            # A simple approximation: 1 token ~= 4 characters.
            # This is a fallback and might not be perfectly accurate.
            # For more precise token counting with Google models, you'd use
            # the generativeai library's count_tokens method.
            return len(string) // 4

        encoding = tiktoken.encoding_for_model(model_name)
        return len(encoding.encode(string))
    except KeyError:
        print(f"Warning: model {model_name} not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    
    return len(encoding.encode(string))

def _calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate the cost of a task based on token usage."""
    if not model_name:
        return 0.0

    # Handle model names with prefixes
    if '/' in model_name:
        model_name = model_name.split('/')[-1]

    pricing = PRICING_DATA.get(model_name)
    if not pricing:
        # Fallback for models with date suffixes like 'gemini-1.5-pro-001'
        base_model_name = '-'.join(model_name.split('-')[:-1])
        if base_model_name:
             pricing = PRICING_DATA.get(base_model_name)
    
    if not pricing:
        # Fallback for models with more complex names like 'gemini-2.0-flash-lite'
        parts = model_name.split('-')
        for i in range(len(parts) - 1, 0, -1):
            base_model_name = '-'.join(parts[:i])
            if PRICING_DATA.get(base_model_name):
                pricing = PRICING_DATA.get(base_model_name)
                break

    if not pricing:
        print(f"Warning: Pricing data not found for model {model_name}. Cost will be 0.")
        return 0.0
        
    input_cost = (prompt_tokens / 1_000_000) * pricing.get("input", 0.0)
    output_cost = (completion_tokens / 1_000_000) * pricing.get("output", 0.0)
    
    # Handle cases where cached_input might not be in the pricing data or is None
    cached_input_price = pricing.get("cached_input")
    cached_input_cost = 0.0
    if cached_input_price is not None:
        cached_input_cost = (prompt_tokens / 1_000_000) * cached_input_price
    
    return input_cost + output_cost + cached_input_cost

def create_log_entry(
    agent_name: str,
    task_description: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    output: str,
    tools_used: List[str]
) -> Dict[str, Any]:
    """Creates a log entry dictionary for monitoring."""
    cost = _calculate_cost(model_name, prompt_tokens, completion_tokens)
    return {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "task": task_description,
        "status": "completed",
        "output": output,
        "tools_used": tools_used,
        "model": model_name,
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost": cost if cost is not None else 0.0,
    }

class CustomChatOpenAI(ChatOpenAI):
    """A custom wrapper for ChatOpenAI to track token usage."""
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def _generate(
        self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs: Any
    ) -> LLMResult:
        """Override the _generate method to capture token usage."""
        response = super()._generate(messages, stop=stop, **kwargs)
        if response.llm_output and 'token_usage' in response.llm_output:
            token_usage = response.llm_output['token_usage']
            self.prompt_tokens += token_usage.get('prompt_tokens', 0)
            self.completion_tokens += token_usage.get('completion_tokens', 0)
        return response
    
    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
