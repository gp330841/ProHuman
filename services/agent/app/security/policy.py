"""Module for policy.py."""
from ..runtime.engine import ToolCall, AgentState, ToolDefinition, AgentConfig
from .sanitizer import InputSanitizer

class PolicyViolation(Exception):
    """Class documentation."""
    pass

class PolicyEngine:
    """Class documentation."""
    def __init__(self, config: AgentConfig, webhook_allowlist: set[str]):
        """Method documentation."""
        self.config = config
        self.webhook_allowlist = webhook_allowlist

    def check(self, tool_call: ToolCall, state: AgentState, tool_def: ToolDefinition):
        """Method documentation."""
        if state.total_hops >= self.config.max_total_hops:
            raise PolicyViolation("Hop cap exceeded")
        if state.tokens_used >= self.config.token_budget_limit:
            raise PolicyViolation("Token budget exceeded")

        InputSanitizer.sanitize(tool_call.arguments, "arguments")

        if tool_call.name == "trigger_external_action":
            target = tool_call.arguments.get("target")
            webhook_config = tool_call.arguments.get("webhook_config")
            if target == "WEBHOOK" and webhook_config:
                url = webhook_config.get("url")
                if url not in self.webhook_allowlist:
                    raise PolicyViolation(f"Webhook URL {url} not in allowlist")

        if tool_def.has_side_effects:
            # Policy check for side effects
            pass
