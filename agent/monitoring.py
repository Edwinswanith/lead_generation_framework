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
        if model_name.startswith("google/"):
            # Use Google's token counter for their models
            prediction_client = aiplatform.gapic.PredictionServiceClient()
            return prediction_client.count_tokens(string).total_tokens
        else:
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
    
    return input_cost + output_cost

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
        "cost": cost,
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

# class MonitoringCrew(Crew):
#     def _execute_tasks(self, tasks: List[Task], **kwargs) -> List[TaskOutput]:
#         task_outputs = []
#         for task in tasks:
#             agent = self._get_agent_to_use(task)
#             if not agent:
#                 raise Exception(f"No agent found for task: {task.description}")

#             # Get the actual LLM and model name
#             actual_llm = getattr(agent.llm, 'llm', agent.llm)
#             model_name = getattr(actual_llm, 'model', 'gpt-4')

#             # Estimate input tokens from task description and context
#             context = self._get_context(task, task_outputs)
#             input_text = task.description + "\n" + context
#             task_prompt_tokens = count_tokens(input_text, model_name)
            
#             # Execute the task
#             output = task.execute_sync(context=context)
#             task_outputs.append(output)

#             # Estimate output tokens from the raw output string
#             output_text = output.raw if output.raw else ""
#             task_completion_tokens = count_tokens(output_text, model_name)
            
#             task_cost = _calculate_cost(model_name, task_prompt_tokens, task_completion_tokens)
            
#             try:
#                 log_entry = create_log_entry(
#                     agent.role,
#                     task.description,
#                     model_name,
#                     task_prompt_tokens,
#                     task_completion_tokens,
#                     output.raw,
#                     [tool.name for tool in getattr(task, "tools", [])]
#                 )
#                 with open(LOG_FILE, "a") as f:
#                     f.write(json.dumps(log_entry) + "\n")
#             except Exception as e:
#                 print(f"Error in _store_execution_log: {e}")

#         return self._create_crew_output(task_outputs)