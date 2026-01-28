"""
LLM-powered Issue Analyzer using LangChain and Claude.

This module uses Claude to analyze GitHub issues and extract:
- Actual difficulty (may differ from labels)
- Time estimates
- Technical requirements
- Clarity scores
- Recommendations

=============================================================================
LANGCHAIN CONCEPTS EXPLAINED
=============================================================================

LangChain is a framework that makes it easier to build applications with LLMs.
Key concepts used in this file:

1. CHAT MODELS (ChatAnthropic)
   - A wrapper around Claude's API
   - Handles the HTTP calls, retries, token counting, etc.
   - You just call it like a function

2. PROMPT TEMPLATES (ChatPromptTemplate)
   - Reusable templates for prompts
   - Use {variables} that get filled in at runtime
   - Separates prompt design from code logic

3. OUTPUT PARSERS (PydanticOutputParser)
   - Converts Claude's text response into structured Python objects
   - Uses Pydantic models to define the expected structure
   - Automatically adds format instructions to the prompt

4. CHAINS (using | pipe operator)
   - Connect components together: prompt | model | parser
   - Data flows through each component
   - Like Unix pipes: cat file.txt | grep "error" | wc -l

=============================================================================
CACHING IN LLM APPLICATIONS
=============================================================================

LLM API calls are:
- SLOW: 1-3 seconds per request
- EXPENSIVE: You pay per token (input + output)
- DETERMINISTIC (with temperature=0): Same input = same output

This makes them PERFECT candidates for caching!

Our caching strategy:
- Cache key includes: issue_id + updated_at + user_preferences
- If the issue hasn't changed and preferences are the same, return cached result
- This can save 90%+ of API costs on repeated searches!

=============================================================================
"""

import os
from typing import List, Tuple, Optional
from datetime import datetime

from anthropic import Anthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .config import MODEL_NAME, TEMPERATURE, MAX_TOKENS
from .github_client import IssueData
from .cache import CacheManager
from .label_mappings import LabelMappingManager

load_dotenv()


# =============================================================================
# PYDANTIC MODEL - Defines the structure of Claude's response
# =============================================================================

class IssueAnalysis(BaseModel):
    """
    Structured output format for issue analysis.

    Pydantic models serve two purposes here:
    1. Define what fields we expect from Claude
    2. Validate that Claude's response matches this structure

    The Field() descriptions help Claude understand what each field means.

    ==========================================================================
    ABOUT LLM CONFIDENCE SCORES
    ==========================================================================

    When we ask Claude for a "confidence" level, it's important to understand
    what this means:

    1. It's SELF-REPORTED, not statistical
       - Claude doesn't have true probability calibration
       - "High confidence" means the LLM sees clear signals in the text

    2. It's based on AVAILABLE INFORMATION
       - Clear issue description + explicit labels = high confidence
       - Vague description + no labels = low confidence

    3. It's USEFUL for filtering
       - High confidence assessments are more reliable
       - Low confidence = maybe ask user to verify

    We ask for confidence on both difficulty and time because:
    - Some issues clearly state "this is a quick fix"
    - Others are vague about scope, making estimation harder
    ==========================================================================
    """

    difficulty: str = Field(
        description="The actual difficulty level: 'beginner', 'intermediate', or 'advanced'"
    )

    difficulty_confidence: str = Field(
        description="How confident is this assessment: 'high', 'medium', or 'low'"
    )

    difficulty_reasoning: str = Field(
        description="Brief explanation of why this difficulty was assigned (1 sentence)",
        default=""
    )

    estimated_time: str = Field(
        description="Time to complete: 'quick_win', 'half_day', 'full_day', 'weekend', or 'deep_dive'"
    )

    time_confidence: str = Field(
        description="How confident is this time estimate: 'high', 'medium', or 'low'",
        default="medium"
    )

    time_reasoning: str = Field(
        description="Brief explanation of the time estimate (1 sentence)"
    )

    summary: str = Field(
        description="2-3 sentence summary of what needs to be done"
    )

    technical_requirements: List[str] = Field(
        description="List of skills/knowledge needed (e.g., ['Python', 'REST APIs', 'pytest'])"
    )

    clarity_score: int = Field(
        description="How clear and actionable is this issue, from 1 (very unclear) to 10 (crystal clear)"
    )

    clarity_reasoning: str = Field(
        description="Brief explanation of the clarity score (1 sentence)",
        default=""
    )

    recommendation: str = Field(
        description="Why this issue is or isn't a good match for the user (1-2 sentences)"
    )


# =============================================================================
# THE ANALYZER CLASS
# =============================================================================

class IssueAnalyzer:
    """
    Analyzes GitHub issues using Claude via LangChain.

    The analysis pipeline:
    1. Take issue data + user preferences
    2. CHECK CACHE - if we've analyzed this before, return cached result
    3. Fill them into a prompt template
    4. Send to Claude
    5. Parse Claude's response into structured IssueAnalysis object
    6. SAVE TO CACHE - for future requests
    """

    def __init__(
        self,
        cache: Optional[CacheManager] = None,
        label_mapper: Optional[LabelMappingManager] = None
    ):
        """
        Initialize the analyzer with LangChain components.

        Args:
            cache: Optional CacheManager instance. If provided, will cache
                   LLM responses to reduce API calls and costs.
            label_mapper: Optional LabelMappingManager for custom label mappings.
                         Used to provide hints to Claude about difficulty.
        """

        # ---------------------------------------------------------------------
        # CACHING LAYER
        # ---------------------------------------------------------------------
        # If cache is provided, we'll use it to avoid redundant API calls
        self.cache = cache

        # ---------------------------------------------------------------------
        # LABEL MAPPINGS
        # ---------------------------------------------------------------------
        # Custom label mappings help us give Claude hints about difficulty
        # based on repository-specific label conventions
        self.label_mapper = label_mapper or LabelMappingManager()

        # ---------------------------------------------------------------------
        # COMPONENT 1: The LLM (Claude)
        # ---------------------------------------------------------------------
        # ChatAnthropic is LangChain's wrapper for Claude
        # It handles: API calls, retries, rate limits, token counting
        self.llm = ChatAnthropic(
            model=MODEL_NAME,           # Which Claude model to use
            temperature=TEMPERATURE,     # 0 = deterministic, 1 = creative
            max_tokens=MAX_TOKENS,      # Max response length
            # API key is auto-read from ANTHROPIC_API_KEY env var
        )

        # ---------------------------------------------------------------------
        # COMPONENT 2: Output Parser
        # ---------------------------------------------------------------------
        # This converts Claude's text response into our IssueAnalysis object
        # It also generates "format instructions" to tell Claude how to respond
        self.parser = PydanticOutputParser(pydantic_object=IssueAnalysis)

        # ---------------------------------------------------------------------
        # COMPONENT 3: Prompt Template
        # ---------------------------------------------------------------------
        # This is the prompt we send to Claude
        # {variables} get filled in at runtime
        self.prompt = ChatPromptTemplate.from_messages([
            # System message: Sets Claude's role and behavior
            ("system", """You are an expert at analyzing GitHub issues to help developers find appropriate open-source contribution opportunities.

Your job is to:
1. Assess the ACTUAL difficulty (which may differ from labels)
2. Estimate realistic completion time
3. Identify required skills
4. Evaluate how clear and actionable the issue is

IMPORTANT - Confidence Assessment:
- Report HIGH confidence when: clear requirements, explicit scope, similar to common patterns
- Report MEDIUM confidence when: some ambiguity, but reasonable assumptions can be made
- Report LOW confidence when: vague description, unclear scope, or unusual requirements

Be realistic and slightly conservative with estimates. It's better to over-estimate time than under-estimate.

{format_instructions}"""),

            # Human message: The actual issue to analyze
            ("human", """Analyze this GitHub issue for a developer looking to contribute:

## Issue Information
- **Title:** {title}
- **Repository:** {repo_name}
- **Stars:** {stars}
- **Labels:** {labels}
- **Created:** {created_at}
- **Comments:** {comments_count}

## Issue Description
{body}

## User Profile
- **Skill Level:** {user_skill}
- **Available Time:** {user_time}

Provide your analysis. For each assessment (difficulty, time, clarity), include:
1. Your rating
2. Your confidence level (high/medium/low)
3. A brief reasoning explaining your assessment""")
        ])

    def _get_label_difficulty_hint(self, issue: IssueData) -> Optional[str]:
        """
        Get a difficulty hint based on issue labels and custom mappings.

        This provides Claude with context about what the labels mean for
        this specific repository.

        Returns:
            A hint string like "Labels suggest BEGINNER difficulty" or None
        """
        if not issue.labels:
            return None

        difficulty = self.label_mapper.get_difficulty_from_labels(
            issue.repo_name,
            issue.labels
        )

        if difficulty:
            # Check if this is from custom/builtin mapping
            if self.label_mapper.has_custom_mapping(issue.repo_name):
                source = "custom mapping"
            elif self.label_mapper.has_builtin_mapping(issue.repo_name):
                source = "known repo pattern"
            else:
                source = "standard labels"

            return f"Labels suggest {difficulty.upper()} difficulty ({source})"

        return None

    def analyze_issue(
        self,
        issue: IssueData,
        user_skill: str,
        user_time: str
    ) -> IssueAnalysis:
        """
        Analyze a single GitHub issue.

        This is where the LangChain "chain" comes together:
        prompt | llm | parser

        WITH CACHING:
        1. First, check if we've analyzed this issue before
        2. If yes (cache hit), return the cached analysis instantly
        3. If no (cache miss), run the chain and save the result

        Args:
            issue: The GitHub issue to analyze
            user_skill: User's skill level (beginner/intermediate/advanced)
            user_time: User's available time (quick_win/half_day/etc)

        Returns:
            IssueAnalysis object with structured analysis
        """

        # ---------------------------------------------------------------------
        # STEP 1: CHECK CACHE
        # ---------------------------------------------------------------------
        # Before calling Claude (which costs time and money), check if we
        # already have a cached analysis for this exact issue + preferences
        if self.cache:
            cached = self.cache.get_llm_analysis(
                issue_id=issue.id,
                repo_name=issue.repo_name,
                issue_updated_at=issue.updated_at,
                user_skill=user_skill,
                user_time=user_time
            )

            if cached:
                # Cache hit! Convert dict back to IssueAnalysis object
                # This saves ~2 seconds and API costs!
                return IssueAnalysis(**cached)

        # ---------------------------------------------------------------------
        # STEP 2: GET LABEL-BASED DIFFICULTY HINT
        # ---------------------------------------------------------------------
        # Use custom label mappings to provide Claude with a hint
        # This improves accuracy for repos with non-standard labels
        label_hint = self._get_label_difficulty_hint(issue)

        # ---------------------------------------------------------------------
        # STEP 3: BUILD THE CHAIN (cache miss - need to call Claude)
        # ---------------------------------------------------------------------
        # The | operator connects components:
        # 1. prompt: fills in variables → produces a prompt
        # 2. llm: sends prompt to Claude → produces text response
        # 3. parser: parses text → produces IssueAnalysis object
        chain = self.prompt | self.llm | self.parser

        # ---------------------------------------------------------------------
        # STEP 4: INVOKE THE CHAIN
        # ---------------------------------------------------------------------
        # Pass in all the variables that the prompt template needs
        # Include the label hint to help Claude make better assessments
        labels_display = ", ".join(issue.labels) if issue.labels else "None"
        if label_hint:
            labels_display += f"\n   [Label hint: {label_hint}]"

        result = chain.invoke({
            "title": issue.title,
            "repo_name": issue.repo_name,
            "stars": issue.repo_stars,
            "labels": labels_display,
            "created_at": issue.created_at.strftime("%Y-%m-%d"),
            "comments_count": issue.comments_count,
            "body": issue.body[:3000] if issue.body else "No description provided",  # Truncate long bodies
            "user_skill": user_skill,
            "user_time": user_time,
            "format_instructions": self.parser.get_format_instructions()
        })

        # ---------------------------------------------------------------------
        # STEP 4: SAVE TO CACHE
        # ---------------------------------------------------------------------
        # Store the result so future requests don't need to call Claude
        if self.cache:
            self.cache.set_llm_analysis(
                issue_id=issue.id,
                repo_name=issue.repo_name,
                issue_updated_at=issue.updated_at,
                user_skill=user_skill,
                user_time=user_time,
                analysis=result.model_dump()  # Convert Pydantic model to dict
            )

        return result

    def analyze_batch(
        self,
        issues: List[IssueData],
        user_skill: str,
        user_time: str,
        progress_callback=None
    ) -> List[Tuple[IssueData, IssueAnalysis]]:
        """
        Analyze multiple issues.

        Args:
            issues: List of issues to analyze
            user_skill: User's skill level
            user_time: User's available time
            progress_callback: Optional function to call with progress updates

        Returns:
            List of (issue, analysis) tuples for successfully analyzed issues
        """

        results = []

        for i, issue in enumerate(issues):
            try:
                if progress_callback:
                    progress_callback(i + 1, len(issues), issue.title)

                analysis = self.analyze_issue(issue, user_skill, user_time)
                results.append((issue, analysis))

            except Exception as e:
                # If one issue fails, continue with the rest
                print(f"  Warning: Failed to analyze '{issue.title[:50]}...': {e}")
                continue

        return results


# =============================================================================
# WHAT HAPPENS UNDER THE HOOD
# =============================================================================
#
# When you call chain.invoke({...}), here's what happens:
#
# 1. PROMPT TEMPLATE fills in variables:
#    "Analyze this GitHub issue..."
#    {title} → "Add input validation to login form"
#    {repo_name} → "facebook/react"
#    etc.
#
# 2. LLM (Claude) receives the filled prompt and generates a response:
#    ```json
#    {
#      "difficulty": "beginner",
#      "estimated_time": "half_day",
#      "summary": "Add validation for email and password fields...",
#      ...
#    }
#    ```
#
# 3. PARSER takes Claude's JSON response and converts it to Python:
#    IssueAnalysis(
#        difficulty="beginner",
#        estimated_time="half_day",
#        summary="Add validation for email and password fields...",
#        ...
#    )
#
# The beauty of LangChain is that all this complexity is hidden behind
# a simple chain.invoke() call.
#
# =============================================================================
