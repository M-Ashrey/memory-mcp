# Dockerfile for memory-mcp — an MCP server providing filesystem-backed persistent
# memory for AI agents. Builds a minimal image that starts the server over stdio
# (the transport Glama's introspection check expects).
FROM python:3.12-slim

WORKDIR /app

# Install the package (pulls the `mcp` dependency declared in pyproject.toml)
COPY . /app
RUN pip install --no-cache-dir .

# memory-mcp persists to the JSON file named by MEMORY_MCP_PATH (defaults to
# ~/.memory-mcp/store.json). Point it at a mountable volume for durability.
ENV MEMORY_MCP_PATH=/data/store.json
VOLUME ["/data"]

# Launch the MCP server over stdio via the console entry point.
ENTRYPOINT ["memory-mcp"]
