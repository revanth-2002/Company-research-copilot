from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict
from urllib.parse import urlparse

import httpx
from langgraph.graph import END, StateGraph

from ..config import get_settings
from ..db import append_progress, get_session, update_session
from ..logger import get_logger

logger = get_logger("workflow")


class ResearchState(TypedDict, total=False):
    session_id: str
    company_name: str
    website: str
    objective: str
    plan: list[str]
    raw_research: dict[str, Any]
    analysis: dict[str, Any]
    report: dict[str, Any]
    quality_score: float
    retries: int
    errors: list[str]


REPORT_SECTIONS = [
    "company_overview",
    "products_services",
    "target_customers",
    "business_signals",
    "risks_challenges",
    "discovery_questions",
    "outreach_strategy",
    "unknowns",
    "sources",
]


def _clean_text(text: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:7000]


def _call_gemini(prompt: str, model: str, api_key: str, max_output_tokens: int = 800) -> str:
    """Call Google GenAI using the official Python client when available.
    Falls back to raising an exception if the client is not installed or the call fails.
    Returns the generated text on success.
    """
    try:
        from google import genai

        client = genai.Client(api_key=api_key) if api_key else genai.Client()
        resp = client.models.generate_content(model=model, contents=prompt)

        # Direct text field if present
        text = getattr(resp, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        # Common output containers
        gens = getattr(resp, "generations", None) or getattr(resp, "candidates", None)
        if isinstance(gens, Sequence) and gens:
            first = gens[0]
            if isinstance(first, Mapping):
                return first.get("text") or first.get("content") or json.dumps(first)
            if hasattr(first, "content"):
                return getattr(first, "content")
            if hasattr(first, "text"):
                return getattr(first, "text")
            return str(first)

        # Some SDKs use a nested `response` or `content` structure
        if hasattr(resp, "response"):
            nested = getattr(resp, "response")
            if isinstance(nested, Mapping):
                return nested.get("text") or nested.get("content") or str(nested)

        if hasattr(resp, "content"):
            content = getattr(resp, "content")
            if isinstance(content, str) and content.strip():
                return content.strip()

        return str(resp)
    except Exception:
        raise


def _fallback_summary(company: str, website: str, objective: str, page_text: str) -> dict[str, Any]:
    domain = urlparse(website).netloc or website
    text_hint = page_text[:600] if page_text else "No homepage text could be fetched during this run."
    return {
        "company_overview": (
            f"{company} is the target account for this research session. The stated objective is: "
            f"{objective}. Public context was gathered from {domain}."
        ),
        "products_services": [
            "Review the company's primary website navigation, product pages, and pricing pages.",
            f"Homepage signal: {text_hint}",
        ],
        "target_customers": [
            "Likely buyers include leaders responsible for the business problem described in the objective.",
            "Validate segment, company size, region, and buying committee during discovery.",
        ],
        "business_signals": [
            "Website positioning and messaging should be compared against recent news, hiring, funding, and customer proof.",
            "High-intent signals include expansion hiring, new product launches, partnerships, and regulatory pressure.",
        ],
        "risks_challenges": [
            "Research may be incomplete without live web search and third-party data providers.",
            "Messaging based only on public pages can miss internal priorities and active initiatives.",
        ],
        "discovery_questions": [
            f"What prompted the team to explore {objective.lower()} now?",
            "Which team owns the initiative and how is success measured?",
            "What tools or processes are currently being used?",
            "What happens if the team does not solve this in the next two quarters?",
        ],
        "outreach_strategy": [
            f"Open with a hypothesis tied to {company}'s public positioning and the meeting objective.",
            "Use one business signal, one risk, and one relevant customer outcome.",
            "Ask for correction early to turn the message into a collaborative discovery conversation.",
        ],
        "unknowns": [
            "Current budget owner",
            "Active vendor stack",
            "Recent strategic initiatives",
            "Timing and urgency",
        ],
        "sources": [{"title": f"{company} website", "url": website}],
    }


def planner_node(state: ResearchState) -> ResearchState:
    session_id = state["session_id"]
    logger.info(f"[{session_id}] Planner node started")
    logger.debug(f"[{session_id}] Company: {state['company_name']}, Objective: {state['objective']}")
    
    append_progress(state["session_id"], "planner", "running", "Breaking the objective into research tasks.")
    
    plan = [
        "Identify company positioning and market category.",
        "Extract products, customer segments, and value propositions.",
        "Find business signals, risks, and open questions.",
        "Convert findings into a seller-ready meeting brief.",
    ]
    
    logger.debug(f"[{session_id}] Research plan created with {len(plan)} tasks")
    append_progress(state["session_id"], "planner", "complete", "Research plan created.", {"plan": plan})
    
    logger.info(f"[{session_id}] Planner node completed")
    return {"plan": plan, "retries": state.get("retries", 0)}


def research_node(state: ResearchState) -> ResearchState:
    session_id = state["session_id"]
    logger.info(f"[{session_id}] Research node started")
    logger.debug(f"[{session_id}] Fetching website: {state['website']}")
    
    append_progress(state["session_id"], "research", "running", "Collecting public website context.")
    errors = state.get("errors", [])
    page_text = ""
    
    try:
        logger.debug(f"[{session_id}] Initiating HTTP request with 8-second timeout")
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            response = client.get(state["website"])
            logger.debug(f"[{session_id}] HTTP response status: {response.status_code}")
            response.raise_for_status()
            page_text = _clean_text(response.text)
            logger.debug(f"[{session_id}] Website text extracted: {len(page_text)} characters")
    except Exception as exc:
        error_msg = f"Website fetch failed: {exc}"
        logger.error(f"[{session_id}] {error_msg}")
        errors.append(error_msg)

    raw_research = {
        "website_text": page_text,
        "sources": [{"title": f"{state['company_name']} website", "url": state["website"]}],
    }
    
    progress_msg = "Research context collected." if page_text else "Proceeding with limited public context."
    logger.info(f"[{session_id}] {progress_msg}")
    
    append_progress(
        state["session_id"],
        "research",
        "complete",
        progress_msg,
        {"characters": len(page_text)},
    )
    
    logger.info(f"[{session_id}] Research node completed")
    return {"raw_research": raw_research, "errors": errors}


def _parse_json_response(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None

    # Try direct JSON parse first. If the model adds surrounding text, extract the JSON object.
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        snippet = text[start : end + 1]
        try:
            parsed = json.loads(snippet)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def analysis_node(state: ResearchState) -> ResearchState:
    session_id = state["session_id"]
    logger.info(f"[{session_id}] Analysis node started")
    
    append_progress(state["session_id"], "analysis", "running", "Synthesizing account insights.")
    page_text = state.get("raw_research", {}).get("website_text", "")
    logger.debug(f"[{session_id}] Website text length for analysis: {len(page_text)} characters")
    
    analysis = _fallback_summary(state["company_name"], state["website"], state["objective"], page_text)
    logger.debug(f"[{session_id}] Using fallback summary as base analysis")

    settings = get_settings()
    if settings.gemini_api_key:
        logger.debug(f"[{session_id}] Gemini API key found, attempting to call Gemini for advanced analysis")
        try:
            prompt = (
                "You are a sales research copilot. Generate a structured research analysis report "
                "for a sales discovery meeting using only the public website text."
                "\n\nRespond with valid JSON only, no markdown, no explanation."
                "\nThe JSON object must contain exactly these keys:"
                " company_overview, products_services, target_customers, business_signals, "
                "risks_challenges, discovery_questions, outreach_strategy, unknowns, sources."
                "\nThe `sources` field must be an array of objects with `title` and `url`."
                "\nUse short arrays for bullet-like sections and text for prose sections."
                f"\n\nCompany: {state['company_name']}"
                f"\nWebsite: {state['website']}"
                f"\nObjective: {state['objective']}"
                f"\nWebsite text: {page_text}"
            )
            logger.debug(f"[{session_id}] Calling Gemini API (model: {settings.gemini_model})")
            response = _call_gemini(prompt, settings.gemini_model, settings.gemini_api_key)
            logger.debug(f"[{session_id}] Gemini response received, parsing JSON")
            parsed = _parse_json_response(response)
            if parsed:
                logger.debug(f"[{session_id}] Successfully parsed Gemini response")
                analysis = parsed
            else:
                logger.warning(f"[{session_id}] Gemini returned invalid JSON response")
                analysis["analysis_error"] = "Gemini returned invalid JSON."
        except Exception as exc:
            logger.error(f"[{session_id}] Gemini analysis failed: {exc}", exc_info=True)
            analysis["analysis_error"] = f"Gemini analysis failed: {exc}"
    else:
        logger.info(f"[{session_id}] No Gemini API key found, using fallback summary only")

    logger.info(f"[{session_id}] Analysis node completed")
    append_progress(state["session_id"], "analysis", "complete", "Initial analysis completed.")
    return {"analysis": analysis}


def quality_node(state: ResearchState) -> ResearchState:
    session_id = state["session_id"]
    logger.info(f"[{session_id}] Quality check node started")
    
    append_progress(state["session_id"], "quality_check", "running", "Checking report completeness.")
    analysis = state.get("analysis", {})
    present = sum(1 for section in REPORT_SECTIONS if analysis.get(section))
    score = present / len(REPORT_SECTIONS)
    
    logger.debug(f"[{session_id}] Quality score: {score:.0%} ({present}/{len(REPORT_SECTIONS)} sections present)")
    logger.debug(f"[{session_id}] Current retries: {state.get('retries', 0)}")
    
    append_progress(
        state["session_id"],
        "quality_check",
        "complete",
        f"Completeness score: {score:.0%}.",
        {"score": score},
    )
    
    logger.info(f"[{session_id}] Quality check node completed")
    return {"quality_score": score, "retries": state.get("retries", 0) + (1 if score < 0.9 else 0)}


def route_after_quality(state: ResearchState) -> str:
    session_id = state.get("session_id", "unknown")
    score = state.get("quality_score", 0)
    retries = state.get("retries", 0)
    
    if score >= 0.9:
        logger.debug(f"[{session_id}] Quality threshold met ({score:.0%}), routing to report_generation")
        return "report_generation"
    
    if retries < 2:
        logger.debug(f"[{session_id}] Quality threshold not met ({score:.0%}), retrying research (retry {retries + 1}/2)")
        return "research"
    
    logger.debug(f"[{session_id}] Max retries reached ({retries}), routing to report_generation anyway")
    return "report_generation"


def report_node(state: ResearchState) -> ResearchState:
    session_id = state["session_id"]
    logger.info(f"[{session_id}] Report generation node started")
    
    append_progress(state["session_id"], "report_generation", "running", "Formatting the final briefing.")
    analysis = state.get("analysis", {})
    
    logger.debug(f"[{session_id}] Formatting analysis into report structure")
    report = {
        "title": f"{state['company_name']} Research Brief",
        "objective": state["objective"],
        "sections": {section: analysis.get(section, "Not enough evidence found.") for section in REPORT_SECTIONS},
        "quality_score": state.get("quality_score", 0),
    }
    
    logger.debug(f"[{session_id}] Report generated with {len(report['sections'])} sections")
    logger.info(f"[{session_id}] Report generation node completed")
    
    append_progress(state["session_id"], "report_generation", "complete", "Structured report generated.")
    return {"report": report}


def build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("planner", planner_node)
    graph.add_node("research", research_node)
    graph.add_node("synthesis", analysis_node)
    graph.add_node("quality_check", quality_node)
    graph.add_node("report_generation", report_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "research")
    graph.add_edge("research", "synthesis")
    graph.add_edge("synthesis", "quality_check")
    graph.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {"research": "research", "report_generation": "report_generation"},
    )
    graph.add_edge("report_generation", END)
    return graph.compile()


research_graph = build_graph()


def run_research_workflow(session_id: str) -> dict[str, Any]:
    logger.info(f"[{session_id}] Research workflow started")
    
    try:
        session = get_session(session_id)
        logger.info(f"[{session_id}] Session loaded - Company: {session['company_name']}")
        logger.debug(f"[{session_id}] Website: {session['website']}, Objective: {session['objective']}")
    except KeyError as exc:
        logger.error(f"[{session_id}] Session not found: {exc}")
        raise
    
    logger.info(f"[{session_id}] Updating session status to running")
    update_session(session_id, status="running", errors=[])
    
    try:
        logger.info(f"[{session_id}] Invoking research graph with state")
        final_state = research_graph.invoke(
            {
                "session_id": session_id,
                "company_name": session["company_name"],
                "website": session["website"],
                "objective": session["objective"],
                "errors": [],
                "retries": 0,
            }
        )
        
        report = final_state["report"]
        logger.info(f"[{session_id}] Workflow completed successfully, updating session with report")
        logger.debug(f"[{session_id}] Report title: {report.get('title')}, Quality score: {report.get('quality_score'):.0%}")
        
        update_session(session_id, status="completed", report=report, errors=final_state.get("errors", []))
        logger.info(f"[{session_id}] Session status updated to completed")
        
        return report
    except Exception as exc:
        logger.error(f"[{session_id}] Workflow failed with error: {exc}", exc_info=True)
        current = get_session(session_id)
        errors = current.get("errors", [])
        errors.append(str(exc))
        update_session(session_id, status="failed", errors=errors)
        logger.error(f"[{session_id}] Session status updated to failed")
        raise


def answer_followup(session_id: str, message: str) -> str:
    chat_logger = get_logger("chat")
    chat_logger.info(f"[{session_id}] Answering followup question")
    chat_logger.debug(f"[{session_id}] Question: {message[:100]}..." if len(message) > 100 else f"[{session_id}] Question: {message}")
    
    settings = get_settings()
    
    try:
        session = get_session(session_id)
        logger.debug(f"[{session_id}] Session retrieved")
    except KeyError:
        logger.warning(f"[{session_id}] Session not found")
        return "The research report is not ready yet. Please wait for the workflow to complete."
    
    report = session.get("report")
    if not report:
        logger.warning(f"[{session_id}] No report available for this session")
        return "The research report is not ready yet. Please wait for the workflow to complete."

    if settings.gemini_api_key:
        logger.debug(f"[{session_id}] Attempting to answer using Gemini API")
        try:
            prompt = (
                "You are a sales research copilot. Answer only from this report context. "
                "If the answer is unknown, say what should be researched next.\n\n"
                f"Report: {report}\n\nQuestion: {message}"
            )
            logger.debug(f"[{session_id}] Calling Gemini with followup question")
            resp = _call_gemini(prompt, settings.gemini_model, settings.gemini_api_key)
            chat_logger.debug(f"[{session_id}] Gemini response received")
            return resp
        except Exception as exc:
            logger.warning(f"[{session_id}] Gemini API call failed: {exc}, falling back to keyword-based answer")

    logger.debug(f"[{session_id}] Using keyword-based fallback for answering")
    lower = message.lower()
    sections = report.get("sections", {})
    
    if "risk" in lower or "challenge" in lower:
        logger.debug(f"[{session_id}] Identified keyword: risk/challenge")
        return _format_answer("Risks and challenges", sections.get("risks_challenges"))
    
    if "question" in lower or "discovery" in lower:
        logger.debug(f"[{session_id}] Identified keyword: question/discovery")
        return _format_answer("Discovery questions", sections.get("discovery_questions"))
    
    if "outreach" in lower or "email" in lower:
        logger.debug(f"[{session_id}] Identified keyword: outreach/email")
        return _format_answer("Outreach strategy", sections.get("outreach_strategy"))
    
    logger.debug(f"[{session_id}] No specific keyword match, using generic answer")
    return (
        f"Based on the report for {session['company_name']}, the best next step is to anchor the conversation "
        f"on the objective: {session['objective']}. Ask a validating question, then use the unknowns section "
        "to decide what to research before the meeting."
    )


def _format_answer(title: str, value: Any) -> str:
    if isinstance(value, list):
        return f"{title}:\n" + "\n".join(f"- {item}" for item in value)
    return f"{title}: {value}"
