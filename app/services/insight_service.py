import json
import logging

from app.services.groq_client import get_client, GROQ_MODEL

logger = logging.getLogger(__name__)

FALLBACK = "Insight could not be generated."


def generate_insight(question: str, sql: str, results: list[dict]) -> str:
    """
    Given the original question, the SQL that ran, and the results,
    explain what the data means in plain English.

    Args:
        question: Original natural language question from the user
        sql: The SQL query that was executed
        results: Query results as a list of dictionaries

    Returns:
        Plain English insight, or a fallback message if generation fails
    """
    logger.info(f"Generating insight for question: {question}")

    # default=str handles dates and Decimals that JSON can't serialize
    results_str = json.dumps(results, indent=2, default=str)

    prompt = f"""You are a business analyst explaining data results to a non-technical audience.

The user asked: {question}

The data returned:
{results_str}

Rules:
1. Only comment on the data you are given. Do not invent comparisons
2. Keep the insight to 2-3 sentences maximum
3. Write for a non-technical business audience
4. Do not mention SQL, tables, or any technical terms
5. If the data shows a trend, describe the direction and magnitude
6. If the data is a single number, put it in business context

Insight:"""

    try:
        response = get_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=600,  # reasoning models spend tokens thinking first
        )

        insight = (response.choices[0].message.content or "").strip()
        if not insight:
            logger.warning("Model returned an empty insight")
            return FALLBACK

        logger.info(f"Insight generated: {insight}")
        return insight

    except Exception as e:
        logger.error(f"Insight generation failed: {e}")
        return FALLBACK