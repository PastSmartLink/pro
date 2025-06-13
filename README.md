# SPORTSΩmegaPRO - The Manna Maker Cognitive OS™️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/) [![Status: Active](https://img.shields.io/badge/status-active-success.svg)](https://github.com/PastSmartLink/pro-main)

**A PhD-Level Cognitive Operating System, Engineered for Google Cloud ADK**

The Manna Maker Cognitive OS™️ is a pioneering multi-agent AI architecture powering strategic intelligence for [SPORTSΩmegaPRO](https://www.sportsomega.com). This repository hosts the PRO-tier engine, a modular system that transforms chaotic data into predictive, narrative-driven **Ωmega Scouting Dossiers**—live in production and designed for scalability.

---

## 📖 Table of Contents

- [Live Ecosystem: Free & PRO Tiers](#-live-ecosystem-free--pro-tiers)
- [Core Innovation: Manna Maker OS](#-core-innovation-manna-maker-os)
- [Functional Blueprint](#%EF%B8%8F-functional-blueprint)
- [Tech Stack & ADK Architecture](#%EF%B8%8F-tech-stack--adk-architecture)
- [Setup and Installation](#%EF%B8%8F-setup-and-installation)
- [What’s Next: The Universal Cognitive OS](#-whats-next-the-universal-cognitive-os--a-declaration-of-intent)
- [Contact](#-contact)

---

## 🚀 Live Ecosystem: Free & PRO Tiers

SPORTSΩmegaPRO operates a two-tiered AI ecosystem, live at [sportsomega.com](https://www.sportsomega.com):

1. **Free Tier**:  
   Accessible via "View Details" on match cards, the free tier uses a Perplexity AI-driven engine to deliver foundational "AI Analyses," showcasing our expertise in sports intelligence.

2. **PRO Tier: Ωmega PRO Scouting Dossier**  
   The "Unlock Ωmega PRO Scouting Dossier" button (Beta, free for now) activates the **Manna Maker Cognitive OS™️**, a Google Cloud ADK-orchestrated engine powered by Google Gemini. It produces premium dossiers with deep tactical insights, surpassing the free tier.

3. **PRO Blueprint Demo**:  
   Explore the Manna Maker’s end-to-end logic at [https://pro-9wil.onrender.com](https://pro-9wil.onrender.com), a production-ready Flask app optimized for Google Cloud ADK.

**Live Demo**: 🌐 [https://pro-9wil.onrender.com](https://pro-9wil.onrender.com)

---

## 💡 Core Innovation: Manna Maker OS

The Manna Maker Cognitive OS™️ is a **Version 3.5 Modular Cognitive Workflow**, redefining AI as a strategic operating system. Inspired by quantum attunement and chaotic navigation, it delivers insights that emerge predictably from complexity.

- 🧠 **Modular CSMP Framework**: A 10-stage **Chief Scout Master Prompt (CSMP)** orchestrates specialized prompts, reducing token usage by 35-45% and enabling A/B testing.
- 🤔 **SUPERGROK Curiosity Engine**: Gemini autonomously generates non-obvious, high-value queries, embodying "quantum attunement" by exploring vast possibility spaces.
- 🔄 **Cognitive Loop**: Iterative research via Perplexity AI and state refinement mirrors "chaotic navigation," uncovering hidden leverage points that reshape analyses.

---

## 🏗️ Functional Blueprint

The blueprint at [https://pro-9wil.onrender.com](https://pro-9wil.onrender.com) demonstrates the Manna Maker’s ADK-native workflow, producing dossiers in 90-115 seconds.

**ADK Architecture Diagram**:

```text
+-------------------------+  1. HTTP Request  +------------------------------+
| Client (sportsomega.com)|------------------>| ADK FastAPI Endpoint         |
| requests dossier for X  |                  | (/api/dossier/generate)      |
+-------------------------+                  +-------------+----------------+
                                                     | 2. Calls Dossier Tool
                                                     v
+--------------------------+  3. Calls Tools  +--------------------------+
| @adk.tool('generate_dossier') |<------------>| @adk.tool('fetch_baseline')  |
| - Executes 10-stage CSMP  |                 | - Wraps data_services.py     |
+--------------------------+                 +--------------------------+
              | 4. Invokes Chief Scout Agent
              v
+--------------------------+  5. Formulates Query  +--------------------------+
| @adk.agent('chief_scout') |--------------------->| @adk.tool('run_perplexity') |
| - Gemini-powered         |                      | - Calls Perplexity AI API   |
| - Manages state          |  6. Integrates Findings +--------------------------+
+--------------------------+     & Refines State
```

This diagram highlights ADK decorators (`@adk.tool`, `@adk.agent`), ensuring native integration with Google Cloud ADK.

---

## 🛠️ Tech Stack & ADK Architecture

- **Core**: Manna Maker Cognitive OS™️ (Proprietary Multi-Agent Framework)
- **Framework**: Google Cloud Agent Development Kit (ADK)
- **AI Models**: Google Gemini (Chief Scout), Perplexity AI (Research Tool)
- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Deployment**: Render.com (Blueprint), Docker
- **Libraries**: `aiohttp`, `python-dotenv`, `tenacity`, `cachetools`

---

## ⚙️ Setup and Installation

### 1. Prerequisites
- Python 3.11+, Git

### 2. Clone Repository
```bash
git clone https://github.com/PastSmartLink/pro-main.git
cd pro-main
```

### 3. Setup Environment
```bash
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 4. 🚨 Configure Environment (IP Protection)
Copy `.env.example` to `.env`. Add secret keys (`PERPLEXITY_API_KEY`, etc.) and populate `CSMP_..._PROMPT` variables with prompt texts from the secure `prompts/` directory.

### 5. Run Service
```bash
# macOS/Linux:
export PYTHONPATH=$(pwd)
# Windows:
set PYTHONPATH=%CD%

uvicorn api.adk_service_api:app --host 0.0.0.0 --port 8001 --reload
```

API available at `http://127.0.0.1:8001`.

---

## 🌌 What’s Next: The Universal Cognitive OS – A Declaration of Intent

The Manna Maker Cognitive OS™️ was never about sports. Sports is simply our first, perfect laboratory—a data-rich, high-stakes environment ideal for proving the power of our engine. This hackathon submission is Milestone 1.

When we present this project, we are implicitly stating:  
*Your Honors, today we present an AI that has mastered the chaotic domain of professional sports. Tomorrow, this exact same engine, retargeted with new data sources and a new domain configuration, will be applied to geopolitical risk, financial markets, and enterprise intelligence.*

This is not a future dream; it is the Universal Strategic Imperative of this project. Our digital 007 agent is not just licensed to analyze sports. It is licensed to analyze anything.

### The "007" Use Case: From Sports to Geopolitics
The mission: analyze the global semiconductor market to produce a "Geopolitical Risk & Supply Chain Volatility Dossier."  
- **Initial Synthesis**: Ingests TSMC production reports, shipping lane data, news from Chinese state media, and commodity prices for rare earth minerals.  
- **The SUPERGROK™️ Inquiry**: The engine moves beyond simple queries. It asks the unasked questions:  
  - "What is the hidden correlation between minor naval drills in the South China Sea and the stock prices of secondary chemical suppliers to Dutch lithography companies?"  
  - "Analyze the sentiment of speeches from China's Ministry of Industry versus internal white papers from Intel to detect a delta in their strategic posturing."  
- **Targeted Execution**: The engine dispatches tools to find specific shipping manifests, track political appointments, and find obscure chemical plant maintenance schedules. The output is actionable, predictive intelligence for hedge funds, governments, and corporations.

### The End-Game: A Domain-Agnostic Platform
You are no longer looking at a sports analysis tool. You are looking at a platform for generating automated intelligence for any domain. The Manna Maker isn't a product; it is the cornerstone of a new category of artificial intelligence. Winning the ADK Hackathon is the crucial first step that validates this vision and makes the larger enterprise possible.

---

## 📄 License

MIT License. See [LICENSE](LICENSE).

---

## 📬 Contact

**Architect**: Hans Johannes Schulte  
**Email**: [pastsmartlink@gmail.com](mailto:pastsmartlink@gmail.com)  
**Devpost**: [devpost.com/pastsmartlink](https://devpost.com/pastsmartlink)  
**GitHub**: [github.com/PastSmartLink/pro-main](https://github.com/PastSmartLink/pro-main)  
**Hackathon**: [Google Cloud ADK Hackathon](https://devpost.com/software/sportsomegapro)