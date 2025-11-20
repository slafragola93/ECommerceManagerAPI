"""
Pydantic error formatter following SOLID principles.

This module provides a clean, performant way to format Pydantic validation errors
in a consistent format matching the application's ValidationException structure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any, Tuple


@dataclass(frozen=True)
class PydanticErrorData:
    """
    Immutable data structure representing categorized Pydantic validation errors.
    
    Attributes:
        missing_fields: List of required fields that are missing
        invalid_fields: Dictionary mapping field names to error messages for invalid values
        type_errors: Dictionary mapping field names to error messages for type mismatches
        constraint_errors: Dictionary mapping field names to error messages for constraint violations
        raw_errors: Complete list of raw Pydantic error dictionaries for debugging
    """
    missing_fields: List[str]
    invalid_fields: Dict[str, str]
    type_errors: Dict[str, str]
    constraint_errors: Dict[str, str]
    raw_errors: List[Dict[str, Any]]


class PydanticErrorParser:
    """
    Parser for Pydantic validation errors following Single Responsibility Principle.
    
    Responsible only for parsing and categorizing Pydantic errors into structured data.
    """
    
    # Mapping of Pydantic error types to categories
    ERROR_TYPE_MAPPING: Dict[str, str] = {
        'missing': 'missing',
        'type_error': 'type_error',
        'value_error': 'value_error',
        'assertion_error': 'constraint',
        'literal_error': 'type_error',
        'enum': 'type_error',
    }
    
    # Keywords that indicate constraint violations
    CONSTRAINT_KEYWORDS: Tuple[str, ...] = (
        'greater', 'less', 'equal', 'min', 'max', 'length',
        'regex', 'pattern', 'multiple', 'divisible'
    )
    
    @staticmethod
    def _extract_field_path(loc: Tuple[Any, ...]) -> str:
        """
        Extract field path from Pydantic location tuple.
        
        Args:
            loc: Location tuple from Pydantic error (e.g., ('body', 'customer', 'email'))
            
        Returns:
            Field path as dot-separated string (e.g., 'customer.email')
            Returns last element if it's a simple field
        """
        if not loc:
            return 'unknown'
        
        # Skip 'body', 'query', 'path', 'header' prefixes
        path_parts = [str(part) for part in loc if part not in ('body', 'query', 'path', 'header')]
        
        if not path_parts:
            return 'unknown'
        
        # If single field, return it directly
        if len(path_parts) == 1:
            return path_parts[0]
        
        # For nested fields, join with dots
        return '.'.join(path_parts)
    
    @staticmethod
    def _categorize_error(error_type: str, error_msg: str) -> str:
        """
        Categorize error based on type and message content.
        
        Args:
            error_type: Pydantic error type (e.g., 'missing', 'type_error.int')
            error_msg: Error message text
            
        Returns:
            Category: 'missing', 'type_error', 'constraint', or 'invalid'
        """
        error_type_lower = error_type.lower()
        
        # Check for missing fields
        if error_type_lower == 'missing':
            return 'missing'
        
        # Check for type errors
        if error_type_lower.startswith('type_error'):
            return 'type_error'
        
        # Check for constraint violations in value_error
        if error_type_lower.startswith('value_error'):
            error_msg_lower = error_msg.lower()
            if any(keyword in error_msg_lower for keyword in PydanticErrorParser.CONSTRAINT_KEYWORDS):
                return 'constraint'
            return 'invalid'
        
        # Check for assertion errors (constraints)
        if error_type_lower.startswith('assertion_error'):
            return 'constraint'
        
        # Default to invalid
        return 'invalid'
    
    @staticmethod
    def parse_errors(pydantic_errors: List[Dict[str, Any]]) -> PydanticErrorData:
        """
        Parse Pydantic validation errors into categorized structure.
        
        Single-pass parsing for optimal performance.
        
        Args:
            pydantic_errors: List of error dictionaries from RequestValidationError.errors()
            
        Returns:
            PydanticErrorData with categorized errors
        """
        missing_fields: List[str] = []
        invalid_fields: Dict[str, str] = {}
        type_errors: Dict[str, str] = {}
        constraint_errors: Dict[str, str] = {}
        
        for error in pydantic_errors:
            loc = error.get('loc', ())
            error_type = error.get('type', 'unknown')
            error_msg = error.get('msg', 'Validation error')
            
            field_path = PydanticErrorParser._extract_field_path(loc)
            category = PydanticErrorParser._categorize_error(error_type, error_msg)
            
            # Format error message for user-friendliness
            formatted_msg = PydanticErrorParser._format_error_message(error_type, error_msg, error.get('input'))
            
            # Categorize into appropriate bucket
            if category == 'missing':
                if field_path not in missing_fields:
                    missing_fields.append(field_path)
            elif category == 'type_error':
                type_errors[field_path] = formatted_msg
            elif category == 'constraint':
                constraint_errors[field_path] = formatted_msg
            else:
                # For invalid fields, only keep the first error per field
                if field_path not in invalid_fields:
                    invalid_fields[field_path] = formatted_msg
        
        return PydanticErrorData(
            missing_fields=sorted(missing_fields),  # Sort for consistency
            invalid_fields=invalid_fields,
            type_errors=type_errors,
            constraint_errors=constraint_errors,
            raw_errors=pydantic_errors
        )
    
    @staticmethod
    def _format_error_message(error_type: str, error_msg: str, input_value: Any = None) -> str:
        """
        Format error message to be user-friendly.
        
        Args:
            error_type: Pydantic error type
            error_msg: Original error message
            input_value: Input value that caused the error (optional)
            
        Returns:
            Formatted error message
        """
        # For type errors, try to extract type information
        if error_type.startswith('type_error'):
            # Extract expected and actual types if available
            if 'expected' in error_msg.lower() or 'got' in error_msg.lower():
                return error_msg
            # Try to infer from error type
            if 'int' in error_type:
                return f"expected int, got {type(input_value).__name__ if input_value is not None else 'None'}"
            elif 'str' in error_type:
                return f"expected str, got {type(input_value).__name__ if input_value is not None else 'None'}"
            elif 'float' in error_type:
                return f"expected float, got {type(input_value).__name__ if input_value is not None else 'None'}"
            elif 'bool' in error_type:
                return f"expected bool, got {type(input_value).__name__ if input_value is not None else 'None'}"
        
        # Return original message for other cases
        return error_msg


class PydanticErrorFormatter:
    """
    Formatter for Pydantic errors following Single Responsibility Principle.
    
    Responsible only for formatting parsed error data into API response format.
    """
    
    @staticmethod
    def format_message(error_data: PydanticErrorData) -> str:
        """
        Generate user-friendly error message from categorized errors.
        
        Uses efficient string building with list join.
        
        Args:
            error_data: Parsed and categorized error data
            
        Returns:
            Formatted error message string
        """
        message_parts: List[str] = []
        
        # Missing fields
        if error_data.missing_fields:
            fields_str = ", ".join(error_data.missing_fields)
            message_parts.append(f"missing fields: {fields_str}")
        
        # Type errors
        if error_data.type_errors:
            type_errors_list = [
                f"{field} ({msg})" 
                for field, msg in error_data.type_errors.items()
            ]
            message_parts.append(f"invalid type for {', '.join(type_errors_list)}")
        
        # Constraint errors
        if error_data.constraint_errors:
            constraint_errors_list = [
                f"{field} ({msg})" 
                for field, msg in error_data.constraint_errors.items()
            ]
            message_parts.append(f"constraint violation for {', '.join(constraint_errors_list)}")
        
        # Invalid fields (catch-all)
        if error_data.invalid_fields:
            invalid_fields_list = [
                f"{field} ({msg})" 
                for field, msg in error_data.invalid_fields.items()
            ]
            message_parts.append(f"invalid value for {', '.join(invalid_fields_list)}")
        
        if not message_parts:
            return "Validation failed"
        
        return f"Validation failed: {'; '.join(message_parts)}"
    
    @staticmethod
    def format_details(error_data: PydanticErrorData) -> Dict[str, Any]:
        """
        Generate structured details dictionary from error data.
        
        Args:
            error_data: Parsed and categorized error data
            
        Returns:
            Dictionary with structured error details
        """
        return {
            "missing_fields": error_data.missing_fields,
            "invalid_fields": error_data.invalid_fields,
            "type_errors": error_data.type_errors,
            "constraint_errors": error_data.constraint_errors,
            "validation_errors": error_data.raw_errors
        }
    
    @staticmethod
    def format(pydantic_errors: List[Dict[str, Any]], error_code: str = "VALIDATION_ERROR") -> Dict[str, Any]:
        """
        Main formatting method that processes and formats Pydantic errors.
        
        Args:
            pydantic_errors: List of error dictionaries from RequestValidationError.errors()
            error_code: Error code to use (default: "VALIDATION_ERROR")
            
        Returns:
            Complete formatted error response dictionary
        """
        # Parse errors in single pass
        error_data = PydanticErrorParser.parse_errors(pydantic_errors)
        
        # Format message
        message = PydanticErrorFormatter.format_message(error_data)
        
        # Format details with structured error information
        details = PydanticErrorFormatter.format_details(error_data)
        
        return {
            "error_code": error_code,
            "message": message,
            "details": details,
            "status_code": 422
        }

