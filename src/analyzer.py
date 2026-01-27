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
"""

import os
from typing import List, Tuple
from datetime import datetime

from anthropic import Anthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .config import MODEL_NAME, TEMPERATURE, MAX_TOKENS
from .github_client import IssueData

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
    """

    difficulty: str = Field(
        description="The actual difficulty level: 'beginner', 'intermediate', or 'advanced'"
    )

    difficulty_confidence: str = Field(
        description="How confident is this assessment: 'high', 'medium', or 'low'"
    )

    estimated_time: str = Field(
        description="Time to complete: 'quick_win', 'half_day', 'full_day', 'weekend', or 'deep_dive'"
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
    2. Fill them into a prompt template
    3. Send to Claude
    4. Parse Claude's response into structured IssueAnalysis object
    """

    def __init__(self):
        """
        Initialize the analyzer with LangChain components.
        """

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

Based on this information, provide your analysis.""")
        ])

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

        Args:
            issue: The GitHub issue to analyze
            user_skill: User's skill level (beginner/intermediate/advanced)
            user_time: User's available time (quick_win/half_day/etc)

        Returns:
            IssueAnalysis object with structured analysis
        """

        # ---------------------------------------------------------------------
        # BUILD THE CHAIN
        # ---------------------------------------------------------------------
        # The | operator connects components:
        # 1. prompt: fills in variables → produces a prompt
        # 2. llm: sends prompt to Claude → produces text response
        # 3. parser: parses text → produces IssueAnalysis object
        chain = self.prompt | self.llm | self.parser

        # ---------------------------------------------------------------------
        # INVOKE THE CHAIN
        # ---------------------------------------------------------------------
        # Pass in all the variables that the prompt template needs
        result = chain.invoke({
            "title": issue.title,
            "repo_name": issue.repo_name,
            "stars": issue.repo_stars,
            "labels": ", ".join(issue.labels) if issue.labels else "None",
            "created_at": issue.created_at.strftime("%Y-%m-%d"),
            "comments_count": issue.comments_count,
            "body": issue.body[:3000] if issue.body else "No description provided",  # Truncate long bodies
            "user_skill": user_skill,
            "user_time": user_time,
            "format_instructions": self.parser.get_format_instructions()
        })

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
