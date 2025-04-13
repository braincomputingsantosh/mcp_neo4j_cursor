# MCP Neo4j Server with Cursor Interface

A Python implementation of a Model-Controller-Processor (MCP) server that connects Neo4j with cursor-based pagination support.

## Overview

This repository contains both server and client components:

- **MCP Server**: A Flask-based REST API that provides a standardized interface to Neo4j
- **Cursor Client**: A Python client library that applications can use to interact with the MCP server

The MCP architecture separates concerns into three layers:

1. **Model** - Handles all Neo4j database interactions
2. **Controller** - Manages API endpoints and request/response handling
3. **Processor** - Contains business logic and data validation

## Features

- Complete CRUD operations for Neo4j nodes and relationships
- Cursor-based pagination for efficient data retrieval
- Custom query execution with parameter binding
- Robust error handling and validation
- Pythonic client interface with mapping and filtering capabilities

## Installation

### Prerequisites

- Python 3.7 or higher
- Neo4j database (local or cloud instance)

### Server Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/braincomputingsantosh/mcp_neo4j_cursor.git
   cd mcp-neo4j-python
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your Neo4j configuration:
   ```
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   PORT=5000
   ```

5. Start the server:
   ```bash
   python app.py
   ```
   
   For production, use Gunicorn or a similar WSGI server:
   ```bash
   gunicorn app:app
   ```

### Client Setup

The client library is included in the `cursor_client.py` file. You can either:

1. Copy this file to your project, or
2. Install this project as a package:
   ```bash
   pip install -e /path/to/mcp-neo4j-python
   ```

## Usage

### Server API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check endpoint |
| `/api/query` | POST | Execute custom Cypher query |
| `/api/<label>/<id>` | GET | Get a node by label and ID |
| `/api/<label>` | POST | Create a new node |
| `/api/<label>/<id>` | PUT | Update a node |
| `/api/<label>/<id>` | DELETE | Delete a node |
| `/api/relationship` | POST | Create a relationship between nodes |
| `/api/cursor/query` | POST | Execute query with pagination |

### Client Examples

#### Basic CRUD Operations

```python
from cursor_client import Neo4jCursorClient

# Initialize client
client = Neo4jCursorClient("http://localhost:5000/api")

# Create a node
person = client.create_node("Person", {
    "id": "123",
    "name": "John Doe",
    "age": 30
})

# Get a node
retrieved = client.get_node("Person", "123")

# Update a node
updated = client.update_node("Person", "123", {
    "age": 31,
    "occupation": "Developer"
})

# Delete a node
client.delete_node("Person", "123")

# Create a relationship
client.create_relationship(
    "Person", "123",
    "Company", "456",
    "WORKS_FOR",
    {"since": 2020}
)
```

#### Using the Cursor

```python
# Create a cursor for paginated query results
person_cursor = client.cursor(
    "MATCH (p:Person) WHERE p.age > $min_age RETURN p",
    {"min_age": 25},
    10  # page size
)

# Get the next page
result = person_cursor.next()
if not result["done"]:
    people = result["value"]
    # Process this page of people...

# Get all results
all_people = person_cursor.all()

# Map results to names
names = person_cursor.map(lambda person: person["p"]["name"])

# Filter results
adults = person_cursor.filter(lambda person: person["p"]["age"] >= 18)

# Iterate through results
for person in person_cursor:
    print(f"Person: {person['p']['name']}")
```

#### Custom Queries

```python
# Execute a custom Cypher query
results = client.execute_query(
    "MATCH (p:Person)-[:WORKS_FOR]->(c:Company) RETURN p, c",
    {}
)
```

## Project Structure

```
mcp-neo4j-python/
├── app.py              # Main Flask application with MCP implementation
├── cursor_client.py    # Client for interacting with the MCP server
├── requirements.txt    # Project dependencies
├── README.md           # This documentation
└── .env                # Environment variables (gitignored)
```

## Extending the Server

### Adding Custom Validations

Edit the `Processor` class in `app.py`:

```python
class Processor:
    @staticmethod
    def validate_node_data(label, data):
        # Add custom validation for your node types
        if label == "CustomNode":
            # Implement your validation logic
            pass
        return {"valid": True}
```

### Adding New Endpoints

Add new routes to `app.py`:

```python
@app.route("/api/custom-endpoint", methods=["GET"])
def custom_endpoint():
    # Implementation
    return jsonify({"result": "success"})
```

## Security Considerations

- Add authentication to protect your API (JWT recommended)
- Use HTTPS in production
- Implement rate limiting for public-facing APIs
- Validate all inputs to prevent Cypher injection attacks

## Performance Tips

- Use cursor-based pagination for large datasets
- Consider adding caching for frequently accessed data
- Use connection pooling in production environments
- Index properties in Neo4j that are frequently queried

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
