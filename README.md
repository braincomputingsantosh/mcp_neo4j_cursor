# Model Context Protocol (MCP) for Cursor AI and Neo4j

This library implements the Model Context Protocol (MCP) to connect Cursor AI with Neo4j graph databases. It provides a standardized interface for Cursor AI to interact with Neo4j, enabling AI-assisted graph database operations.

## Overview

The implementation consists of two main components:

1. **MCPNeo4jConnector**: A low-level connector that implements the Model Context Protocol specification for Neo4j.

2. **CursorAINeo4jConnector**: A higher-level connector specifically designed for Cursor AI integration, providing simplified methods for common operations.

## Features

- Execute Cypher queries against Neo4j databases
- Retrieve database schema information (node labels, relationship types, properties)
- Support for transactions (begin, commit, rollback)
- Proper handling of Neo4j-specific data types
- Error handling with descriptive messages
- Compatible with the Cursor AI interface

## Installation

### Prerequisites

- Python 3.7+
- Neo4j database (4.0+)
- Cursor AI environment

### Installation Steps

1. Install required dependencies:

```bash
pip install neo4j python-dotenv
```

2. Create a `.env` file with your Neo4j credentials:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

3. Download or copy the `mcp_cursor_neo4j.py` file to your project.

## Basic Usage

```python
from mcp_cursor_neo4j import CursorAINeo4jConnector

# Connect to Neo4j (uses .env file by default)
cursor = CursorAINeo4jConnector()

# Execute a Cypher query
results = cursor.execute("MATCH (n:Person) RETURN n.name AS name, n.age AS age")

# Print results
for row in results:
    print(f"Name: {row['name']}, Age: {row['age']}")

# Close connection when done
cursor.close()
```

## Connecting to Neo4j

You can connect to Neo4j using environment variables or by explicitly providing connection details:

```python
# Using environment variables (.env file)
cursor = CursorAINeo4jConnector()

# Explicitly providing connection details
cursor = CursorAINeo4jConnector(
    uri="bolt://localhost:7687",
    username="neo4j",
    password="your_password"
)
```

## Querying Neo4j

### Basic Queries

```python
# Simple query
results = cursor.execute("MATCH (n) RETURN n LIMIT 10")

# Query with parameters
results = cursor.execute(
    "MATCH (p:Person) WHERE p.age > $min_age RETURN p.name AS name",
    {"min_age": 30}
)
```

### Working with Results

Results are returned as a list of dictionaries:

```python
results = cursor.execute("MATCH (n:Movie) RETURN n.title AS title, n.year AS year")
for movie in results:
    print(f"{movie['title']} ({movie['year']})")
```

### Working with Neo4j Nodes and Relationships

The results preserve Neo4j-specific data structures:

```python
results = cursor.execute("MATCH (p:Person)-[r:ACTED_IN]->(m:Movie) RETURN p, r, m LIMIT 1")

for row in results:
    person = row['p']
    relationship = row['r']
    movie = row['m']
    
    print(f"Actor: {person['properties']['name']}")
    print(f"Role: {relationship['properties'].get('role', 'Unknown')}")
    print(f"Movie: {movie['properties']['title']}")
```

## Transactions

For multiple write operations, use transactions to ensure data consistency:

```python
# Begin a transaction
cursor.begin()

try:
    # Execute multiple operations
    cursor.execute_in_transaction(
        "CREATE (p:Person {name: $name, age: $age})",
        {"name": "John Doe", "age": 30}
    )
    
    cursor.execute_in_transaction(
        "CREATE (m:Movie {title: $title, year: $year})",
        {"title": "Example Movie", "year": 2023}
    )
    
    cursor.execute_in_transaction(
        "MATCH (p:Person {name: $person_name}), (m:Movie {title: $movie_title}) "
        "CREATE (p)-[:ACTED_IN {role: $role}]->(m)",
        {
            "person_name": "John Doe",
            "movie_title": "Example Movie",
            "role": "Main Character"
        }
    )
    
    # Commit the transaction
    cursor.commit()
    
except Exception as e:
    # Rollback on error
    cursor.rollback()
    print(f"Transaction failed: {str(e)}")
```

## Schema Information

Retrieve information about the database schema:

```python
# Get all node labels
labels = cursor.get_node_labels()

# Get all relationship types
relationship_types = cursor.get_relationship_types()

# Get properties for a specific node label
person_properties = cursor.get_node_properties("Person")
print(f"Person properties: {person_properties}")

# Get properties for a specific relationship type
acted_in_properties = cursor.get_relationship_properties("ACTED_IN")
print(f"ACTED_IN properties: {acted_in_properties}")

# Get connected node labels for a relationship type
from_labels, to_labels = cursor.get_connected_labels("ACTED_IN")
print(f"ACTED_IN connects: {from_labels} → {to_labels}")
```

## Database Information

Get information about the connected Neo4j database:

```python
db_info = cursor.get_database_info()
print(f"Neo4j version: {db_info['info']['version']}")
print(f"Edition: {db_info['info']['edition']}")
```

## Advanced Usage: Direct MCP Access

For advanced use cases, you can access the underlying MCP connector directly:

```python
# Access the underlying MCP connector
mcp = cursor.mcp

# Use MCP protocol methods directly
info = mcp.info()
schema = mcp.get_schema()
query_result = mcp.query("MATCH (n) RETURN count(n) AS node_count")

print(f"Node count: {query_result['rows'][0]['node_count']}")
```

## Error Handling

The connector provides meaningful error messages:

```python
try:
    # Attempt an invalid query
    cursor.execute("MATCH (n:NonExistentLabel) WHERE n.missing > 10 RETURN n")
except Exception as e:
    print(f"Query error: {str(e)}")
```

## Integration with Cursor AI

This connector is designed to be used with Cursor AI for advanced graph database interactions:

```python
# Example of how Cursor AI might use this connector
def analyze_graph_with_cursor_ai(query):
    # Connect to Neo4j
    connector = CursorAINeo4jConnector()
    
    try:
        # Execute the query
        results = connector.execute(query)
        
        # Process results with Cursor AI
        # (Cursor AI integration code would go here)
        
        return results
    finally:
        connector.close()
```

## Environment File Example

Create a `.env` file with the following content:

```
# Neo4j Connection
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_password

# Optional Configuration
# CURSOR_AI_API_KEY=your_cursor_ai_api_key
# NEO4J_DATABASE=neo4j
```

## Limitations

- This implementation doesn't support Neo4j's subscription-based (reactive) queries
- Database multi-tenancy is not fully implemented
- Some advanced Neo4j features may not be fully exposed through the MCP interface

## License

MIT License
