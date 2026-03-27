"""Content filtering module - filters low-quality content before LLM evaluation."""
from __future__ import annotations

import re
from typing import Tuple

from .logger import get_logger


class ContentFilter:
    """Filters content to reduce LLM calls on low-quality text."""
    
    # Minimum content length (increased from 50 to 200)
    MIN_CONTENT_LENGTH = 200
    
    # Relevant keywords for AI/startup/product ideas
    RELEVANT_KEYWORDS = {
        # AI/ML related
        "ai", "artificial intelligence", "machine learning", "ml", "deep learning",
        "neural network", "nlp", "computer vision", "llm", "gpt", "automation",
        "chatbot", "generative", "ai-powered", "ai-driven",
        
        # Startup/business related
        "startup", "business", "entrepreneur", "venture", "founder", "company",
        "market", "industry", "product-market fit", "mvp", "scale", "growth",
        
        # Product/app related
        "product", "app", "application", "software", "platform", "tool", "solution",
        "saas", "service", "feature", "user experience", "ux",
        
        # Idea/innovation related
        "idea", "innovation", "solution", "opportunity", "concept", "proposal",
        "brainstorm", "creative", "novel", "disrupt",
        
        # Tech related
        "tech", "technology", "software", "api", "integration", "cloud",
        "data", "analytics", "algorithm",
    }
    
    # Boilerplate patterns (navigation, footer, legal content)
    BOILERPLATE_PATTERNS = [
        # Navigation patterns
        r"home\s*\|\s*about\s*\|\s*contact",
        r"home\s*\|\s*about\s*\|\s*services",
        r"menu\s+home\s+about",
        r"navigation\s+menu",
        
        # Footer patterns
        r"copyright\s*©?\s*\d{4}",
        r"all\s+rights\s+reserved",
        r"privacy\s+policy",
        r"terms\s+of\s+service",
        r"terms\s+and\s+conditions",
        r"cookie\s+policy",
        
        # Common boilerplate phrases
        r"subscribe\s+to\s+our\s+newsletter",
        r"follow\s+us\s+on\s+(twitter|facebook|linkedin|instagram)",
        r"sign\s+up\s+for\s+our\s+newsletter",
        r"contact\s+us\s+today",
        r"learn\s+more\s+about\s+our\s+services",
    ]
    
    # Compile patterns for efficiency
    BOILERPLATE_REGEX = re.compile("|".join(BOILERPLATE_PATTERNS), re.IGNORECASE)
    
    @classmethod
    def is_content_worthy(cls, text: str, url: str = "") -> Tuple[bool, str]:
        """
        Check if content is worthy of LLM evaluation.
        
        Args:
            text: The text content to evaluate
            url: Optional source URL for context
            
        Returns:
            Tuple of (is_worthy: bool, reason: str)
            - is_worthy: True if content passes all filters
            - reason: Explanation if filtered, empty string if worthy
        """
        logger = get_logger()
        
        # Filter 1: Minimum content length
        if len(text) < cls.MIN_CONTENT_LENGTH:
            reason = f"Content too short: {len(text)} chars (min {cls.MIN_CONTENT_LENGTH})"
            logger.debug(f"Filtered content from {url}: {reason}")
            return False, reason
        
        # Filter 2: Keyword relevance
        has_keywords, keyword_reason = cls._check_keyword_relevance(text)
        if not has_keywords:
            logger.debug(f"Filtered content from {url}: {keyword_reason}")
            return False, keyword_reason
        
        # Filter 3: Language detection (English-only)
        is_english, lang_reason = cls._check_language(text)
        if not is_english:
            logger.debug(f"Filtered content from {url}: {lang_reason}")
            return False, lang_reason
        
        # Filter 4: Boilerplate ratio check
        is_quality, boiler_reason = cls._check_boilerplate_ratio(text)
        if not is_quality:
            logger.debug(f"Filtered content from {url}: {boiler_reason}")
            return False, boiler_reason
        
        return True, ""
    
    @classmethod
    def _check_keyword_relevance(cls, text: str) -> Tuple[bool, str]:
        """
        Check if text contains relevant keywords.
        
        Returns:
            Tuple of (has_keywords, reason)
        """
        text_lower = text.lower()
        
        # Count how many relevant keywords are present
        keyword_count = sum(1 for kw in cls.RELEVANT_KEYWORDS if kw in text_lower)
        
        # Require at least 2 relevant keywords for short content (< 500 chars)
        # Require at least 1 relevant keyword for longer content
        min_keywords = 2 if len(text) < 500 else 1
        
        if keyword_count < min_keywords:
            return False, f"Insufficient relevant keywords: found {keyword_count}, need {min_keywords}"
        
        return True, ""
    
    @classmethod
    def _check_language(cls, text: str) -> Tuple[bool, str]:
        """
        Check if text appears to be English.
        
        Uses simple heuristics:
        - ASCII character ratio
        - Common English word patterns
        
        Returns:
            Tuple of (is_english, reason)
        """
        if not text:
            return False, "Empty text"
        
        # Calculate ASCII ratio
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        ascii_ratio = ascii_chars / len(text)
        
        # Require high ASCII ratio for English (allowing some special chars)
        if ascii_ratio < 0.85:
            return False, f"Non-English content: ASCII ratio {ascii_ratio:.2%}"
        
        # Check for common English words (quick heuristic)
        text_lower = text.lower()
        common_english = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can",
            "and", "or", "but", "if", "then", "else", "when", "where",
            "what", "which", "who", "whom", "whose", "this", "that",
            "these", "those", "for", "to", "of", "in", "on", "at", "by",
        }
        
        # Split into words and check for English patterns
        words = set(re.findall(r'\b[a-z]+\b', text_lower))
        english_word_count = len(words & common_english)
        
        # Require at least 3 common English words
        if english_word_count < 3:
            return False, f"Non-English content: only {english_word_count} common English words"
        
        return True, ""
    
    @classmethod
    def _check_boilerplate_ratio(cls, text: str) -> Tuple[bool, str]:
        """
        Check if text has too much boilerplate content.
        
        Returns:
            Tuple of (is_quality, reason)
        """
        if not text:
            return False, "Empty text"
        
        # Find all boilerplate matches
        matches = cls.BOILERPLATE_REGEX.findall(text)
        
        # Calculate boilerplate ratio
        # Each match contributes to boilerplate score
        boilerplate_chars = sum(len(m) for m in matches)
        boilerplate_ratio = boilerplate_chars / len(text)
        
        # Allow up to 30% boilerplate content
        max_boilerplate_ratio = 0.30
        
        if boilerplate_ratio > max_boilerplate_ratio:
            return False, f"Too much boilerplate: {boilerplate_ratio:.1%} (max {max_boilerplate_ratio:.0%})"
        
        # Also check for excessive repetition of boilerplate patterns
        if len(matches) > 5:
            return False, f"Too many boilerplate patterns: {len(matches)} matches"
        
        return True, ""
    
    @classmethod
    def get_filter_stats(cls, text: str, url: str = "") -> dict:
        """
        Get detailed filter statistics for debugging.
        
        Returns:
            Dictionary with filter statistics
        """
        is_worthy, reason = cls.is_content_worthy(text, url)
        
        # Calculate individual metrics
        text_lower = text.lower()
        keyword_count = sum(1 for kw in cls.RELEVANT_KEYWORDS if kw in text_lower)
        
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        ascii_ratio = ascii_chars / len(text) if text else 0
        
        matches = cls.BOILERPLATE_REGEX.findall(text)
        boilerplate_chars = sum(len(m) for m in matches)
        boilerplate_ratio = boilerplate_chars / len(text) if text else 0
        
        common_english = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can",
            "and", "or", "but", "if", "then", "else", "when", "where",
            "what", "which", "who", "whom", "whose", "this", "that",
            "these", "those", "for", "to", "of", "in", "on", "at", "by",
        }
        words = set(re.findall(r'\b[a-z]+\b', text_lower))
        english_word_count = len(words & common_english)
        
        return {
            "is_worthy": is_worthy,
            "reason": reason,
            "content_length": len(text),
            "keyword_count": keyword_count,
            "ascii_ratio": ascii_ratio,
            "english_word_count": english_word_count,
            "boilerplate_ratio": boilerplate_ratio,
            "boilerplate_matches": len(matches),
        }