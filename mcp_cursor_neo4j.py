# mcp_cursor_neo4j.py

import os
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MCPNeo4jConnector:
    """
    Model Context Protocol connector for Cursor AI to Neo4j
    This class implements the MCP specification for connecting Cursor AI to Neo4j databases
    """
    
    def __init__(self, uri: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the MCP connector with Neo4j credentials
        
        Args:
            uri: Neo4j connection URI (bolt://host:port)
            username: Neo4j username
            password: Neo4j password
        """
        # Use passed credentials or fall back to environment variables
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        
        # Initialize the Neo4j driver
        self.driver = GraphDatabase.driver(
            self.uri, 
            auth=(self.username, self.password)
        )
        
        # Standard MCP properties
        self.mcp_version = "1.0"
        self.capabilities = {
            "query": True,
            "schema": True,
            "transaction": True,
            "write": True,
            "subscribe": False  # Neo4j doesn't support native subscriptions in this implementation
        }
    
    def close(self):
        """Close the Neo4j driver connection"""
        self.driver.close()
    
    def _format_record(self, record) -> Dict[str, Any]:
        """Format a Neo4j record into a dictionary"""
        result = {}
        for key in record.keys():
            # Handle Neo4j types appropriately
            value = record[key]
            
            # If it's a Neo4j Node, extract properties
            if hasattr(value, 'labels') and hasattr(value, 'items'):
                # It's a Node
                result[key] = {
                    "__type": "node",
                    "labels": list(value.labels),
                    "properties": dict(value.items()),
                    "id": value.id if hasattr(value, 'id') else None
                }
            # If it's a Neo4j Relationship, extract properties
            elif hasattr(value, 'type') and hasattr(value, 'items'):
                # It's a Relationship
                result[key] = {
                    "__type": "relationship",
                    "type": value.type,
                    "properties": dict(value.items()),
                    "id": value.id if hasattr(value, 'id') else None,
                    "start_node_id": value.start_node.id if hasattr(value, 'start_node') else None,
                    "end_node_id": value.end_node.id if hasattr(value, 'end_node') else None
                }
            # If it's a Path, extract nodes and relationships
            elif hasattr(value, 'nodes') and hasattr(value, 'relationships'):
                # It's a Path
                nodes = []
                for node in value.nodes:
                    nodes.append({
                        "__type": "node",
                        "labels": list(node.labels),
                        "properties": dict(node.items()),
                        "id": node.id if hasattr(node, 'id') else None
                    })
                
                relationships = []
                for rel in value.relationships:
                    relationships.append({
                        "__type": "relationship",
                        "type": rel.type,
                        "properties": dict(rel.items()),
                        "id": rel.id if hasattr(rel, 'id') else None,
                        "start_node_id": rel.start_node.id if hasattr(rel, 'start_node') else None,
                        "end_node_id": rel.end_node.id if hasattr(rel, 'end_node') else None
                    })
                
                result[key] = {
                    "__type": "path",
                    "nodes": nodes,
                    "relationships": relationships
                }
            else:
                # Regular value (string, number, boolean, etc.)
                result[key] = value
        
        return result
    
    # MCP Protocol methods
    
    def info(self) -> Dict[str, Any]:
        """
        Get information about the MCP connector
        
        Returns:
            Dict with MCP version, capabilities, and database info
        """
        # Get Neo4j version and other server info
        db_info = {}
        with self.driver.session() as session:
            result = session.run("CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition")
            record = result.single()
            if record:
                db_info = {
                    "name": record["name"],
                    "version": record["versions"][0] if record["versions"] else "unknown",
                    "edition": record["edition"]
                }
        
        return {
            "mcp_version": self.mcp_version,
            "capabilities": self.capabilities,
            "database": {
                "type": "neo4j",
                "info": db_info
            }
        }
    
    def query(self, query_text: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a Cypher query on Neo4j
        
        Args:
            query_text: Cypher query string
            params: Optional parameters for the query
            
        Returns:
            Dict with rows (results) and metadata
        """
        params = params or {}
        
        try:
            with self.driver.session() as session:
                result = session.run(query_text, params)
                records = []
                
                # Collect all records, formatting each one
                for record in result:
                    records.append(self._format_record(record))
                
                # Get query summary
                summary = result.consume()
                
                # Prepare metadata
                metadata = {
                    "query_time_ms": summary.result_available_after + summary.result_consumed_after,
                    "row_count": len(records),
                    "has_more": False,  # All results returned at once in this implementation
                }
                
                # Add counters if this was a write query
                if summary.counters:
                    counter_data = {}
                    counter_dict = summary.counters._asdict()
                    for key, value in counter_dict.items():
                        if value:  # Only include non-zero counters
                            counter_data[key] = value
                    
                    if counter_data:
                        metadata["counters"] = counter_data
                
                return {
                    "rows": records,
                    "metadata": metadata
                }
                
        except Exception as e:
            # Format error according to MCP protocol
            return {
                "error": {
                    "message": str(e),
                    "code": "NEO4J_ERROR",
                    "details": {
                        "query": query_text,
                        "params": params
                    }
                },
                "rows": [],
                "metadata": {
                    "row_count": 0
                }
            }
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the Neo4j database schema
        
        Returns:
            Dict with node labels, relationship types, and properties
        """
        schema = {
            "nodes": {},
            "relationships": {}
        }
        
        try:
            # Get node labels and properties
            with self.driver.session() as session:
                # Get all node labels
                label_result = session.run("CALL db.labels()")
                labels = [record["label"] for record in label_result]
                
                # For each label, get properties
                for label in labels:
                    # Sample a node with this label to get its properties
                    property_result = session.run(
                        f"MATCH (n:{label}) RETURN n LIMIT 1"
                    )
                    record = property_result.single()
                    
                    if record and record["n"]:
                        node_properties = dict(record["n"].items())
                        property_types = {
                            k: type(v).__name__ for k, v in node_properties.items()
                        }
                        schema["nodes"][label] = {
                            "properties": property_types
                        }
                    else:
                        schema["nodes"][label] = {
                            "properties": {}
                        }
                
                # Get all relationship types
                rel_result = session.run("CALL db.relationshipTypes()")
                rel_types = [record["relationshipType"] for record in rel_result]
                
                # For each relationship type, get properties and connected node labels
                for rel_type in rel_types:
                    # Sample a relationship with this type to get its properties
                    rel_property_result = session.run(
                        f"MATCH ()-[r:{rel_type}]->() RETURN r LIMIT 1"
                    )
                    record = rel_property_result.single()
                    
                    if record and record["r"]:
                        rel_properties = dict(record["r"].items())
                        property_types = {
                            k: type(v).__name__ for k, v in rel_properties.items()
                        }
                        
                        # Find which node labels this relationship connects
                        connected_labels_result = session.run(
                            f"MATCH (a)-[r:{rel_type}]->(b) "
                            f"RETURN labels(a) AS from_labels, labels(b) AS to_labels "
                            f"LIMIT 5"
                        )
                        
                        from_labels = set()
                        to_labels = set()
                        
                        for label_record in connected_labels_result:
                            from_labels.update(label_record["from_labels"])
                            to_labels.update(label_record["to_labels"])
                        
                        schema["relationships"][rel_type] = {
                            "properties": property_types,
                            "connects": [list(from_labels), list(to_labels)]
                        }
                    else:
                        schema["relationships"][rel_type] = {
                            "properties": {},
                            "connects": [[], []]
                        }
                
                return {
                    "schema": schema,
                    "metadata": {
                        "node_label_count": len(labels),
                        "relationship_type_count": len(rel_types)
                    }
                }
                
        except Exception as e:
            # Format error according to MCP protocol
            return {
                "error": {
                    "message": str(e),
                    "code": "SCHEMA_ERROR"
                },
                "schema": {
                    "nodes": {},
                    "relationships": {}
                },
                "metadata": {}
            }
    
    def begin_transaction(self) -> Dict[str, Any]:
        """
        Begin a new transaction
        
        Returns:
            Dict with transaction ID
        """
        try:
            # Create a new transaction session
            tx_session = self.driver.session()
            tx = tx_session.begin_transaction()
            
            # Store transaction and session objects (implementation detail)
            tx_id = str(id(tx))
            self._transactions = getattr(self, '_transactions', {})
            self._transactions[tx_id] = (tx_session, tx)
            
            return {
                "transaction_id": tx_id,
                "metadata": {
                    "status": "active"
                }
            }
        except Exception as e:
            return {
                "error": {
                    "message": str(e),
                    "code": "TRANSACTION_ERROR"
                }
            }
    
    def commit_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Commit a transaction
        
        Args:
            transaction_id: ID of the transaction to commit
            
        Returns:
            Dict with success status
        """
        try:
            self._transactions = getattr(self, '_transactions', {})
            if transaction_id not in self._transactions:
                return {
                    "error": {
                        "message": f"Transaction {transaction_id} not found",
                        "code": "INVALID_TRANSACTION"
                    }
                }
            
            session, tx = self._transactions[transaction_id]
            tx.commit()
            session.close()
            
            # Remove from active transactions
            del self._transactions[transaction_id]
            
            return {
                "transaction_id": transaction_id,
                "metadata": {
                    "status": "committed"
                }
            }
        except Exception as e:
            # Try to roll back on error
            try:
                if transaction_id in self._transactions:
                    session, tx = self._transactions[transaction_id]
                    tx.rollback()
                    session.close()
                    del self._transactions[transaction_id]
            except:
                pass
                
            return {
                "error": {
                    "message": str(e),
                    "code": "COMMIT_ERROR"
                }
            }
    
    def rollback_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Rollback a transaction
        
        Args:
            transaction_id: ID of the transaction to rollback
            
        Returns:
            Dict with success status
        """
        try:
            self._transactions = getattr(self, '_transactions', {})
            if transaction_id not in self._transactions:
                return {
                    "error": {
                        "message": f"Transaction {transaction_id} not found",
                        "code": "INVALID_TRANSACTION"
                    }
                }
            
            session, tx = self._transactions[transaction_id]
            tx.rollback()
            session.close()
            
            # Remove from active transactions
            del self._transactions[transaction_id]
            
            return {
                "transaction_id": transaction_id,
                "metadata": {
                    "status": "rolled_back"
                }
            }
        except Exception as e:
            return {
                "error": {
                    "message": str(e),
                    "code": "ROLLBACK_ERROR"
                }
            }
    
    def query_in_transaction(self, transaction_id: str, query_text: str, 
                             params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a query within an existing transaction
        
        Args:
            transaction_id: ID of the transaction
            query_text: Cypher query string
            params: Optional parameters for the query
            
        Returns:
            Dict with rows (results) and metadata
        """
        params = params or {}
        
        try:
            self._transactions = getattr(self, '_transactions', {})
            if transaction_id not in self._transactions:
                return {
                    "error": {
                        "message": f"Transaction {transaction_id} not found",
                        "code": "INVALID_TRANSACTION"
                    },
                    "rows": [],
                    "metadata": {
                        "row_count": 0
                    }
                }
            
            _, tx = self._transactions[transaction_id]
            result = tx.run(query_text, params)
            
            records = []
            for record in result:
                records.append(self._format_record(record))
            
            # Get summary
            summary = result.consume()
            
            # Prepare metadata
            metadata = {
                "query_time_ms": summary.result_available_after + summary.result_consumed_after,
                "row_count": len(records),
                "has_more": False,
                "transaction_id": transaction_id,
                "status": "active"
            }
            
            # Add counters if this was a write query
            if summary.counters:
                counter_data = {}
                counter_dict = summary.counters._asdict()
                for key, value in counter_dict.items():
                    if value:  # Only include non-zero counters
                        counter_data[key] = value
                
                if counter_data:
                    metadata["counters"] = counter_data
            
            return {
                "rows": records,
                "metadata": metadata
            }
                
        except Exception as e:
            # Format error according to MCP protocol
            return {
                "error": {
                    "message": str(e),
                    "code": "TRANSACTION_QUERY_ERROR",
                    "details": {
                        "query": query_text,
                        "params": params,
                        "transaction_id": transaction_id
                    }
                },
                "rows": [],
                "metadata": {
                    "row_count": 0,
                    "transaction_id": transaction_id
                }
            }

# Cursor AI Integration Layer
class CursorAINeo4jConnector:
    """
    Cursor AI connector for Neo4j using the Model Context Protocol
    """
    
    def __init__(self, uri: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the Cursor AI connector
        
        Args:
            uri: Neo4j connection URI
            username: Neo4j username
            password: Neo4j password
        """
        self.mcp = MCPNeo4jConnector(uri, username, password)
        self.active_tx = None
    
    def close(self):
        """Close the connection"""
        self.mcp.close()
    
    # Cursor AI specific methods
    
    def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return results as a list of dictionaries
        
        Args:
            query: Cypher query
            params: Optional query parameters
            
        Returns:
            List of result dictionaries
        """
        result = self.mcp.query(query, params)
        if "error" in result:
            raise Exception(f"Query error: {result['error']['message']}")
        return result["rows"]
    
    def get_node_labels(self) -> List[str]:
        """Get all node labels in the database"""
        schema_result = self.mcp.get_schema()
        if "error" in schema_result:
            raise Exception(f"Schema error: {schema_result['error']['message']}")
        return list(schema_result["schema"]["nodes"].keys())
    
    def get_relationship_types(self) -> List[str]:
        """Get all relationship types in the database"""
        schema_result = self.mcp.get_schema()
        if "error" in schema_result:
            raise Exception(f"Schema error: {schema_result['error']['message']}")
        return list(schema_result["schema"]["relationships"].keys())
    
    def begin(self) -> None:
        """Begin a transaction"""
        if self.active_tx:
            raise Exception("Transaction already active")
        
        result = self.mcp.begin_transaction()
        if "error" in result:
            raise Exception(f"Transaction error: {result['error']['message']}")
        
        self.active_tx = result["transaction_id"]
    
    def commit(self) -> None:
        """Commit the active transaction"""
        if not self.active_tx:
            raise Exception("No active transaction")
        
        result = self.mcp.commit_transaction(self.active_tx)
        if "error" in result:
            raise Exception(f"Commit error: {result['error']['message']}")
        
        self.active_tx = None
    
    def rollback(self) -> None:
        """Rollback the active transaction"""
        if not self.active_tx:
            raise Exception("No active transaction")
        
        result = self.mcp.rollback_transaction(self.active_tx)
        if "error" in result:
            raise Exception(f"Rollback error: {result['error']['message']}")
        
        self.active_tx = None
    
    def execute_in_transaction(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a query within the active transaction
        
        Args:
            query: Cypher query
            params: Optional query parameters
            
        Returns:
            List of result dictionaries
        """
        if not self.active_tx:
            raise Exception("No active transaction")
        
        result = self.mcp.query_in_transaction(self.active_tx, query, params)
        if "error" in result:
            raise Exception(f"Transaction query error: {result['error']['message']}")
        
        return result["rows"]

    def get_node_properties(self, label: str) -> Dict[str, str]:
        """
        Get all properties for a specific node label
        
        Args:
            label: Node label
            
        Returns:
            Dictionary mapping property names to their types
        """
        schema_result = self.mcp.get_schema()
        if "error" in schema_result:
            raise Exception(f"Schema error: {schema_result['error']['message']}")
        
        if label not in schema_result["schema"]["nodes"]:
            return {}
        
        return schema_result["schema"]["nodes"][label]["properties"]
    
    def get_relationship_properties(self, rel_type: str) -> Dict[str, str]:
        """
        Get all properties for a specific relationship type
        
        Args:
            rel_type: Relationship type
            
        Returns:
            Dictionary mapping property names to their types
        """
        schema_result = self.mcp.get_schema()
        if "error" in schema_result:
            raise Exception(f"Schema error: {schema_result['error']['message']}")
        
        if rel_type not in schema_result["schema"]["relationships"]:
            return {}
        
        return schema_result["schema"]["relationships"][rel_type]["properties"]
    
    def get_connected_labels(self, rel_type: str) -> Tuple[List[str], List[str]]:
        """
        Get the node labels connected by a specific relationship type
        
        Args:
            rel_type: Relationship type
            
        Returns:
            Tuple of (from_labels, to_labels)
        """
        schema_result = self.mcp.get_schema()
        if "error" in schema_result:
            raise Exception(f"Schema error: {schema_result['error']['message']}")
        
        if rel_type not in schema_result["schema"]["relationships"]:
            return ([], [])
        
        connects = schema_result["schema"]["relationships"][rel_type]["connects"]
        return (connects[0], connects[1])

    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the Neo4j database"""
        info_result = self.mcp.info()
        if "error" in info_result:
            raise Exception(f"Info error: {info_result['error']['message']}")
        
        return info_result["database"]

# Example usage
if __name__ == "__main__":
    # Connect to Neo4j
    connector = CursorAINeo4jConnector()
    
    try:
        # Get database info
        db_info = connector.get_database_info()
        print(f"Connected to Neo4j {db_info['info']['version']} {db_info['info']['edition']}")
        
        # Get schema information
        labels = connector.get_node_labels()
        rel_types = connector.get_relationship_types()
        
        print(f"Node labels: {labels}")
        print(f"Relationship types: {rel_types}")
        
        # Execute a query
        results = connector.execute("MATCH (n) RETURN n LIMIT 5")
        print(f"Query returned {len(results)} results")
        
        # Use a transaction
        connector.begin()
        try:
            # Create a new node
            connector.execute_in_transaction(
                "CREATE (n:TestNode {name: $name, created: datetime()})",
                {"name": "Test Node from Cursor AI"}
            )
            
            # Commit the transaction
            connector.commit()
            print("Transaction committed successfully")
        except Exception as e:
            # Rollback on error
            connector.rollback()
            print(f"Transaction rolled back: {str(e)}")
    
    finally:
        # Close the connection
        connector.close()