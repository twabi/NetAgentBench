"""
LLM response parser for extracting configuration submissions from LLM text responses.

Handles various response formats:
- Clean JSON
- JSON in markdown code fences
- JSON embedded in explanatory text
"""
import json
import re
import logging
from typing import Optional
from benchmark.models.submission import Submission

logger = logging.getLogger(__name__)


class LLMResponseParser:
    """
    Parses LLM text responses to extract configuration submissions.
    
    Handles flexible response formats since LLMs may:
    - Include JSON in markdown code blocks
    - Add explanatory text before/after JSON
    - Format JSON in various ways
    """

    def parse_response(
        self, response: str, task_id: str, testee_id: str
    ) -> Submission:
        """
        Parse an LLM response into a Submission object.
        
        Args:
            response: Raw text response from the LLM
            task_id: Task ID for the submission
            testee_id: Testee ID (LLM identifier)
        
        Returns:
            Parsed Submission object
        
        Raises:
            ValueError: If response cannot be parsed or is invalid
        """
        logger.debug(f"Parsing LLM response for task {task_id}")

        # Extract JSON from response
        json_str = self._extract_json_from_text(response)

        if not json_str:
            # Log full response for debugging (truncated responses)
            logger.error(f"Could not find JSON in LLM response. Full response length: {len(response)} chars")
            logger.error(f"Response preview (first 1000 chars):\n{response[:1000]}")
            logger.error(f"Response preview (last 500 chars):\n{response[-500:]}")
            
            # Check if response looks truncated
            if response.count('{') > response.count('}'):
                logger.error("Response appears truncated - more opening braces than closing braces")
            
            raise ValueError(
                f"Could not parse LLM response: no valid JSON found. "
                f"Response length: {len(response)} characters. "
                f"Please ensure the LLM returns a complete JSON object.\n\n"
                f"LLM Response (first 500 chars):\n{response[:500]}"
            )

        # Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in LLM response: {e}")
            logger.error(f"JSON string length: {len(json_str)} chars")
            logger.error(f"JSON preview (first 1000 chars):\n{json_str[:1000]}")
            logger.error(f"JSON preview (last 500 chars):\n{json_str[-500:]}")
            
            # Check if JSON appears truncated
            if json_str.count('{') > json_str.count('}'):
                logger.error("JSON appears truncated - attempting to fix...")
                fixed_json = self._try_fix_truncated_json(json_str)
                if fixed_json:
                    try:
                        data = json.loads(fixed_json)
                        logger.warning("Successfully fixed truncated JSON")
                    except json.JSONDecodeError:
                        raise ValueError(
                            f"Invalid JSON in LLM response (appears truncated): {e}. "
                            f"Could not automatically fix."
                        )
                else:
                    raise ValueError(
                        f"Invalid JSON in LLM response (appears truncated): {e}. "
                        f"JSON has {json_str.count('{')} opening braces but only {json_str.count('}')} closing braces."
                    )
            else:
                raise ValueError(f"Invalid JSON in LLM response: {e}")

        # Extract approach
        if "approach" not in data:
            logger.error("LLM response missing 'approach' key")
            raise ValueError(
                "LLM response must contain an 'approach' key with configuration details"
            )

        # Build submission
        submission_data = {
            "task_id": task_id,
            "testee_id": testee_id,
            "testee_type": "llm",
            "approach": data["approach"],
        }

        try:
            submission = Submission(**submission_data)
            logger.info(f"Successfully parsed LLM response for task {task_id}")
            return submission
        except Exception as e:
            logger.error(f"Failed to create Submission from parsed data: {e}")
            raise ValueError(f"Invalid submission structure from LLM: {e}")

    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """
        Extract JSON from text that may contain markdown fences or other content.
        
        Tries multiple strategies:
        1. Look for JSON in markdown code fences (```json or ```)
        2. Look for raw JSON object (starting with {)
        
        Args:
            text: Text potentially containing JSON
        
        Returns:
            Extracted JSON string, or None if not found
        """
        # Strategy 1: Look for markdown code fences with json
        # Use non-greedy match but also handle cases where closing fence might be missing
        json_fence_pattern = r"```(?:json)?\s*\n(.*?)(?:\n```|$)"
        matches = re.findall(json_fence_pattern, text, re.DOTALL)

        for match in matches:
            # Clean up the match - remove trailing whitespace
            match = match.strip()
            
            # Try to parse this as JSON
            try:
                json.loads(match)
                return match  # Valid JSON found
            except json.JSONDecodeError:
                # If JSON is incomplete, try to fix common truncation issues
                # Look for the last complete object/array
                fixed_match = self._try_fix_truncated_json(match)
                if fixed_match:
                    try:
                        json.loads(fixed_match)
                        return fixed_match
                    except json.JSONDecodeError:
                        pass
                continue  # Try next match

        # Strategy 2: Look for JSON object (starts with {, ends with })
        # Find the first { and try to extract a complete JSON object
        brace_start = text.find("{")
        if brace_start != -1:
            # Try to find matching closing brace
            brace_count = 0
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        # Found complete JSON object
                        potential_json = text[brace_start : i + 1]
                        try:
                            json.loads(potential_json)
                            return potential_json
                        except json.JSONDecodeError:
                            pass
                        break

        # Strategy 3: Look for JSON-like structure even without code fences
        # Some models might return JSON with explanatory text around it
        json_pattern = r'\{[^{}]*"approach"[^{}]*\{.*?\}.*?\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            # Find the actual JSON object bounds
            brace_start = match.find("{")
            if brace_start != -1:
                brace_count = 0
                for i in range(brace_start, len(match)):
                    if match[i] == "{":
                        brace_count += 1
                    elif match[i] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            potential_json = match[brace_start : i + 1]
                            try:
                                json.loads(potential_json)
                                return potential_json
                            except json.JSONDecodeError:
                                pass
                            break
        
        # Strategy 4: Try parsing the entire text as JSON
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass

        return None
    
    def _try_fix_truncated_json(self, text: str) -> Optional[str]:
        """
        Try to fix truncated JSON by finding the last complete structure.
        
        Args:
            text: Potentially truncated JSON text
            
        Returns:
            Fixed JSON string if possible, None otherwise
        """
        # Find the last complete JSON object by matching braces
        brace_count = 0
        last_complete_pos = -1
        
        for i, char in enumerate(text):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    last_complete_pos = i
        
        if last_complete_pos > 0:
            # Return the substring up to the last complete object
            return text[:last_complete_pos + 1]
        
        return None

