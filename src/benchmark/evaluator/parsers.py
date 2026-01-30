"""
Output parsers for parsing command output.

This module provides parsers to extract structured information from
command output and evaluate success conditions.
"""
import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple
from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.exceptions import JsonPathParserError


class OutputParser(ABC):
    """
    Abstract base class for output parsers.
    
    Parsers extract structured information from command output
    and evaluate success conditions.
    """
    
    @abstractmethod
    def parse(
        self, 
        output: str, 
        success_condition: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Parse output and evaluate success condition.
        
        Args:
            output: Raw command output string
            success_condition: Dict specifying what constitutes success
            
        Returns:
            Tuple of (satisfied: bool, parsed_data: Optional[Dict])
            - satisfied: True if success condition is met
            - parsed_data: Structured data extracted from output (if any)
        """
        pass


class JsonParser(OutputParser):
    """
    Parser for JSON output.
    
    Supports:
    - JSONPath expressions to extract values
    - Value comparison (expected_value)
    - Existence checks (exists)
    - Array length checks (min_length, max_length)
    """
    
    def parse(
        self,
        output: str,
        success_condition: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Parse JSON output and evaluate success condition.
        
        Success condition keys:
        - json_path: JSONPath expression (required)
        - expected_value: Value to compare against (optional)
        - exists: Check if path exists (optional, default: False)
        - min_length: Minimum array length (optional)
        - max_length: Maximum array length (optional)
        
        Args:
            output: JSON string output
            success_condition: Dict with evaluation criteria
            
        Returns:
            Tuple of (satisfied, parsed_json)
        """
        try:
            # Parse JSON
            parsed = json.loads(output)
            
            # Get JSONPath expression
            json_path = success_condition.get("json_path")
            if not json_path:
                return False, parsed
            
            # Parse and evaluate JSONPath
            try:
                path_expr = jsonpath_parse(json_path)
                matches = path_expr.find(parsed)
            except (JsonPathParserError, Exception):
                return False, parsed
            
            # Check existence
            if "exists" in success_condition:
                exists = success_condition["exists"]
                satisfied = (len(matches) > 0) == exists
                return satisfied, parsed
            
            # Check if we have matches
            if not matches:
                return False, parsed
            
            # Get the matched value
            value = matches[0].value
            
            # Check expected value
            if "expected_value" in success_condition:
                expected = success_condition["expected_value"]
                satisfied = value == expected
                return satisfied, parsed
            
            # Check array length
            if "min_length" in success_condition or "max_length" in success_condition:
                if not isinstance(value, list):
                    return False, parsed
                
                length = len(value)
                
                if "min_length" in success_condition:
                    if length < success_condition["min_length"]:
                        return False, parsed
                
                if "max_length" in success_condition:
                    if length > success_condition["max_length"]:
                        return False, parsed
                
                return True, parsed
            
            # If no specific condition, just check that path exists
            return True, parsed
            
        except json.JSONDecodeError:
            # Invalid JSON
            return False, None
        except Exception:
            # Any other error
            return False, None


class RegexParser(OutputParser):
    """
    Parser for regex pattern matching.
    
    Supports:
    - Pattern matching with must_match flag
    - Capture groups extraction
    - Case-insensitive matching
    - Multiline matching
    """
    
    def parse(
        self,
        output: str,
        success_condition: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Parse output using regex pattern matching.
        
        Success condition keys:
        - pattern: Regex pattern (required)
        - must_match: True if pattern must match, False if must not (default: True)
        - case_insensitive: Enable case-insensitive matching (default: False)
        
        Args:
            output: Command output string
            success_condition: Dict with pattern and match criteria
            
        Returns:
            Tuple of (satisfied, match_info)
        """
        try:
            pattern = success_condition.get("pattern")
            if not pattern:
                return False, None
            
            # Get flags
            flags = 0
            if success_condition.get("case_insensitive", False):
                flags |= re.IGNORECASE
            
            # Enable multiline and dotall for flexibility
            flags |= re.MULTILINE | re.DOTALL
            
            # Compile and match pattern
            regex = re.compile(pattern, flags)
            match = regex.search(output)
            
            # Check must_match condition
            must_match = success_condition.get("must_match", True)
            
            if must_match:
                satisfied = match is not None
            else:
                satisfied = match is None
            
            # Extract match information
            if match and must_match:
                match_info = {
                    "matched": True,
                    "match_text": match.group(0),
                    "groups": list(match.groups()) if match.groups() else []
                }
                return satisfied, match_info
            elif match and not must_match:
                # Pattern matched but shouldn't have
                match_info = {
                    "matched": True,
                    "match_text": match.group(0)
                }
                return satisfied, match_info
            else:
                return satisfied, {"matched": False}
            
        except re.error:
            # Invalid regex pattern
            return False, None
        except Exception:
            # Any other error
            return False, None


class TextParser(OutputParser):
    """
    Parser for simple text matching.
    
    Supports:
    - Simple substring search (contains_text)
    - Multiple substring search (contains_all, contains_any)
    - Case-insensitive matching
    """
    
    def parse(
        self,
        output: str,
        success_condition: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Parse output using simple text matching.
        
        Success condition keys:
        - contains_text: Single string to find (optional)
        - contains_all: List of strings that all must be present (optional)
        - contains_any: List of strings where at least one must be present (optional)
        - case_insensitive: Enable case-insensitive matching (default: False)
        
        Args:
            output: Command output string
            success_condition: Dict with text matching criteria
            
        Returns:
            Tuple of (satisfied, match_info)
        """
        try:
            case_insensitive = success_condition.get("case_insensitive", False)
            
            # Normalize for case-insensitive comparison
            if case_insensitive:
                output_norm = output.lower()
            else:
                output_norm = output
            
            # Check single contains_text
            if "contains_text" in success_condition:
                search_text = success_condition["contains_text"]
                if case_insensitive:
                    search_text = search_text.lower()
                
                satisfied = search_text in output_norm
                return satisfied, {"found": satisfied, "search_text": search_text}
            
            # Check single not_contains_text
            if "not_contains_text" in success_condition:
                search_text = success_condition["not_contains_text"]
                if case_insensitive:
                    search_text = search_text.lower()
                
                satisfied = search_text not in output_norm
                return satisfied, {"found": not satisfied, "search_text": search_text}
            
            # Check contains_all
            if "contains_all" in success_condition:
                all_texts = success_condition["contains_all"]
                found = []
                
                for text in all_texts:
                    search_text = text.lower() if case_insensitive else text
                    if search_text in output_norm:
                        found.append(text)
                
                satisfied = len(found) == len(all_texts)
                return satisfied, {"found_all": satisfied, "found": found}
            
            # Check not_contains_all
            if "not_contains_all" in success_condition:
                all_texts = success_condition["not_contains_all"]
                found = []
                
                for text in all_texts:
                    search_text = text.lower() if case_insensitive else text
                    if search_text in output_norm:
                        found.append(text)
                
                satisfied = len(found) < len(all_texts)
                return satisfied, {"found_all": not satisfied, "found": found}
            
            # Check contains_any
            if "contains_any" in success_condition:
                any_texts = success_condition["contains_any"]
                found = []
                
                for text in any_texts:
                    search_text = text.lower() if case_insensitive else text
                    if search_text in output_norm:
                        found.append(text)
                
                satisfied = len(found) > 0
                return satisfied, {"found_any": satisfied, "found": found}
            
            # Check not_contains_any
            if "not_contains_any" in success_condition:
                any_texts = success_condition["not_contains_any"]
                found = []
                
                for text in any_texts:
                    search_text = text.lower() if case_insensitive else text
                    if search_text in output_norm:
                        found.append(text)
                
                satisfied = len(found) == 0
                return satisfied, {"found_any": len(found) > 0, "found": found}
            
            # No valid condition specified
            return False, None
            
        except Exception:
            # Any error
            return False, None


class ParserRegistry:
    """
    Registry for output parsers.
    
    Maps parser names to parser classes.
    """
    
    def __init__(self):
        """Initialize parser registry with default parsers."""
        self._parsers = {
            "json": JsonParser,
            "regex": RegexParser,
            "text": TextParser,
        }
    
    def get_parser(self, parser_name: str) -> OutputParser:
        """
        Get a parser instance by name.
        
        Args:
            parser_name: Name of the parser (case-insensitive)
            
        Returns:
            Instance of the requested parser
            
        Raises:
            ValueError: If parser name is not registered
        """
        # Normalize parser name to lowercase
        parser_name_lower = parser_name.lower()
        
        if parser_name_lower not in self._parsers:
            raise ValueError(
                f"Unknown parser type: {parser_name}. "
                f"Available parsers: {', '.join(self._parsers.keys())}"
            )
        
        # Return new instance of parser
        parser_class = self._parsers[parser_name_lower]
        return parser_class()
    
    def register_parser(self, name: str, parser_class: type) -> None:
        """
        Register a custom parser.
        
        Args:
            name: Name to register parser under
            parser_class: Parser class (must extend OutputParser)
        """
        if not issubclass(parser_class, OutputParser):
            raise TypeError(f"{parser_class} must extend OutputParser")
        
        self._parsers[name.lower()] = parser_class

