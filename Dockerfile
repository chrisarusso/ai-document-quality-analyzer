FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
COPY rulesets/ rulesets/

# Install dependencies
RUN uv sync --frozen

# Expose port
EXPOSE 8080

# Run the app
CMD ["uv", "run", "uvicorn", "doc_analyzer.api:app", "--host", "0.0.0.0", "--port", "8080"]
