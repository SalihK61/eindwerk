# FileAnalyzer

A Dockerized Flask web application that lets authenticated users upload CSV files, explore basic and AI-driven insights, visualize statistics and correlations, and generate PDF reports.

---

## Table of Contents

- [Features](#features)  
- [Tech Stack](#tech-stack)  
- [Prerequisites](#prerequisites)  
- [Configuration](#configuration)  
- [Installation & Running](#installation--running)  
  - [1. Clone & Environment](#1-clone--environment)  
  - [2. Build & Run with Docker Compose](#2-build--run-with-docker-compose)  
  - [3. Direct Docker Build & Run](#3-direct-docker-build--run)  
- [Usage](#usage)  
- [Project Structure](#project-structure)  
- [Contributing](#contributing)  
- [License](#license)  

---

## Features

- **User Authentication** via Auth0 (signup/login/logout)  
- **CSV Upload & Storage**: Persist user-uploaded CSVs in PostgreSQL  
- **Data Profiling**:  
  - Column data types, counts, missing values, duplicates  
  - Basic descriptive statistics  
  - Correlation matrix with interactive HTML  
  - Histograms & category plots  
- **AI Insights**: Summarize dataset using OpenAI API  
- **PDF Reports**: Automatically generate and download styled PDF analyses  
- **Dashboard & History**: View past CSVs and generated reports  

---

## Tech Stack

- **Backend:** Python 3.11, Flask, Flask-SQLAlchemy, Authlib, python-dotenv  
- **Database:** PostgreSQL 15  
- **ORM:** SQLAlchemy  
- **Authentication:** Auth0  
- **AI Integration:** OpenAI Python SDK  
- **Reporting:** FPDF  
- **Visualization:** Matplotlib, Seaborn, Tailwind CSS  
- **Containerization:** Docker, Docker Compose  
- **Server:** Gunicorn  

---

## Prerequisites

- [Docker >= 20.10](https://docs.docker.com/get-docker/)  
- [Docker Compose >= 1.29](https://docs.docker.com/compose/)  
- (Optional) An Auth0 account for OIDC configuration  
- (Optional) An OpenAI API key  

---

## Configuration

Create a `.env` file in the project root (or rename the included `.ENV`) with the following variables:

```dotenv
# Flask
FLASK_ENV=production
FLASK_SECRET_KEY=⟨your-flask-secret⟩

# Auth0 (or your OIDC provider)
AUTH0_DOMAIN=⟨your-auth0-domain⟩
AUTH0_CLIENT_ID=⟨your-auth0-client-id⟩
AUTH0_CLIENT_SECRET=⟨your-auth0-client-secret⟩
AUTH0_CALLBACK_URL=http://localhost:4000/callback

# PostgreSQL
POSTGRES_USER=csvuser
POSTGRES_PASSWORD=csvpass
POSTGRES_DB=csvdb
DATABASE_URL=postgresql://csvuser:csvpass@db:5432/csvdb

# OpenAI
OPENAI_API_KEY=sk-...
