# Groww Mutual Fund RAG Chatbot

An AI-powered Retrieval-Augmented Generation (RAG) chatbot built for answering factual mutual fund queries using official Groww mutual fund pages as the primary data source.

The system retrieves and indexes mutual fund information daily, enabling users to chat with updated scheme-related data in a conversational manner.

## Features

- AI-powered factual Q&A for mutual funds
- Built using Retrieval-Augmented Generation (RAG)
- Uses `bge-small-en` embedding model for semantic search
- Uses ChromaDB as the vector database
- Daily automated scraping and indexing of latest mutual fund data using a scheduler
- Supports adding any Groww mutual fund URL dynamically for contextual chat
- Fast inference powered by Groq LLM API
- Frontend inspired by Groww’s actual design system
- Responsive and clean UI built using Google Stitch

---

# Tech Stack

## AI / Backend
- Embedding Model: `bge-small-en`
- LLM Inference: Groq API
- Vector Database: ChromaDB
- Framework: Python
- RAG Pipeline: Custom implementation

## Frontend
- Google Stitch
- Groww-inspired UI/UX Design System

## Data Pipeline
- Web scraping for mutual fund data extraction
- Automated scheduler for daily data refresh and re-indexing

---

# How It Works

1. The system scrapes mutual fund information from Groww mutual fund pages.
2. Extracted content is cleaned and converted into embeddings using `bge-small-en`.
3. Embeddings are stored inside ChromaDB.
4. User queries are converted into embeddings and matched against the vector database.
5. Relevant context is retrieved and passed to the Groq LLM API.
6. The chatbot generates a factual response strictly grounded in retrieved data.

---

# Dynamic Fund Support

Users can provide any valid Groww mutual fund link, and the chatbot can:

- Scrape the page
- Index the content
- Add it to the vector database
- Enable contextual question-answering for that scheme

This makes the system scalable across multiple mutual funds without requiring manual dataset creation.

---

# Important Disclaimer

This chatbot does NOT provide:

- Investment advice
- Financial recommendations
- Buy/Sell suggestions
- Portfolio guidance

The assistant is strictly designed for factual information retrieval and question-answering based on publicly available mutual fund data.

Responses are generated only from retrieved context and are intended for informational purposes only.

---

# Use Cases

- Mutual fund scheme exploration
- Fund fact retrieval
- Expense ratio and returns lookup
- Scheme comparison support
- Educational financial Q&A
- AI-powered financial information assistant

---

# Future Improvements

- Multi-AMC support
- PDF factsheet ingestion
- Portfolio analysis support
- Advanced filtering and search
- User authentication and saved chats
- Hybrid search (BM25 + semantic retrieval)
- Real-time NAV updates

---

# Architecture Overview

User Query → Embedding Generation → ChromaDB Retrieval → Context Injection → Groq LLM Response

Daily Scheduler → Scraping → Data Cleaning → Embedding Creation → ChromaDB Update

---

# Model & Infrastructure

- Embedding Model: `BAAI/bge-small-en`
- Vector Store: ChromaDB
- LLM Provider: Groq
- Scheduler: Automated periodic refresh pipeline

---

# Objective

The goal of this project is to build a reliable, scalable, and factual AI assistant for mutual fund information retrieval while avoiding hallucinated financial advice.
