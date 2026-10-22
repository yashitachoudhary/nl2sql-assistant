---
title: NL2SQL Analytics Assistant
emoji: 📊
colorFrom: blue
colorTo: purple
sdk: streamlit
sdk_version: 1.35.0
app_file: streamlit_app.py
pinned: false
---

# 📊 NL2SQL Analytics Assistant

Ask your database questions in plain English. Get numbers, charts, and AI-written insights in seconds — no SQL knowledge needed.

## What it does

- Connects to MySQL, PostgreSQL, or a built-in demo database
- Converts natural language questions into validated SQL automatically
- Renders results as metric cards, line charts, or bar charts
- Generates plain English business insights from the data

## Try it instantly

Click **Try the demo database** to explore a sample SaaS startup dataset with 6 tables and 18 months of data. No credentials needed.

## Connect your own database

Supports MySQL and PostgreSQL. Use a **read-only database user** — the tool only runs SELECT queries, but a read-only user adds a second layer of safety.

## Example questions

- How many users signed up each month?
- What is the daily active user count for the last 7 days?
- Show revenue growth by month
- How many connections are accepted vs pending?
- What is the average session duration?

## Tech stack

- **Frontend:** Streamlit
- **LLM:** Groq API (openai/gpt-oss-20b)
- **Database:** SQLAlchemy (MySQL, PostgreSQL, SQLite)
- **Charts:** Plotly
- **Data:** Pandas

## Architecture
User question (plain English)
↓
LLM (Groq) generates SQL using your schema
↓
SQL safety validator (SELECT only, no dangerous keywords)
↓
Query runs against your database
↓
Results rendered as chart + table + AI insight


## Privacy

- Database credentials are held in session memory only — never stored or logged
- Only table and column names are sent to the Groq API for SQL generation
- Row data is only sent to Groq if AI insights are enabled (toggle in sidebar)
- Use a read-only database user for maximum safety

## Built by

MBA student in Big Data Analytics — built as a learning project to explore
LLM application architecture, prompt engineering, and full-stack Python development.