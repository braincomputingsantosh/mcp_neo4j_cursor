# app.py
from flask import Flask, request, jsonify
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
config = {
    "neo4j": {
        "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        "username": os.getenv("NEO4J_USER", "neo4j"),
        "password": os.getenv("NEO4J_PASSWORD", "password")
    }
}

# Model Layer
class Neo4jModel:
    def __init__(self, uri, username, password):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        self.driver.close()

    def execute_query(self, query, params=None):
        if params is None:
            params = {}
        
        with self.driver.session() as session:
            result = session.run(query, params)
            records = []
            for record in result:
                record_dict = {}
                for key in record.keys():
                    record_dict[key] = record[key]
                records.append(record_dict)
            return records

    def get_node(self, label, node_id):
        query = f"MATCH (n:{label} {{id: $id}}) RETURN n"
        return self.execute_query(query, {"id": node_id})

    def create_node(self, label, properties):
        props_string = ", ".join([f"{key}: ${key}" for key in properties.keys()])
        query = f"CREATE (n:{label} {{{props_string}}}) RETURN n"
        return self.execute_query(query, properties)

    def update_node(self, label, node_id, properties):
        props_string = ", ".join([f"n.{key} = ${key}" for key in properties.keys()])
        query = f"MATCH (n:{label} {{id: $id}}) SET {props_string} RETURN n"
        params = {"id": node_id, **properties}
        return self.execute_query(query, params)

    def delete_node(self, label, node_id):
        query = f"MATCH (n:{label} {{id: $id}}) DETACH DELETE n"
        return self.execute_query(query, {"id": node_id})

    def create_relationship(self, from_label, from_id, to_label, to_id, rel_type, properties=None):
        if properties is None:
            properties = {}
        
        props_string = ""
        if properties:
            props_list = [f"{key}: ${key}" for key in properties.keys()]
            props_string = f" {{{', '.join(props_list)}}}"
        
        query = f"""
        MATCH (from:{from_label} {{id: $from_id}}), (to:{to_label} {{id: $to_id}})
        CREATE (from)-[r:{rel_type}{props_string}]->(to)
        RETURN from, r, to
        """
        params = {"from_id": from_id, "to_id": to_id, **properties}
        return self.execute_query(query, params)

# Initialize Neo4j Model
model = Neo4jModel(
    config["neo4j"]["uri"],
    config["neo4j"]["username"],
    config["neo4j"]["password"]
)

# Processor Layer
class Processor:
    @staticmethod
    def validate_node_data(label, data):
        # Implement validation logic based on node label
        if label == "Person":
            if "name" not in data:
                return {"valid": False, "errors": ["Name is required"]}
        elif label == "Product":
            errors = []
            if "title" not in data:
                errors.append("Title is required")
            if "price" not in data:
                errors.append("Price is required")
            if errors:
                return {"valid": False, "errors": errors}
        # Add more label-specific validations as needed
        return {"valid": True}

    # Add more processing methods as needed

# Controller Layer - API Routes
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})

@app.route("/api/query", methods=["POST"])
def execute_query():
    data = request.json
    query = data.get("query")
    params = data.get("params", {})
    
    try:
        result = model.execute_query(query, params)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/<label>/<node_id>", methods=["GET"])
def get_node(label, node_id):
    try:
        result = model.get_node(label, node_id)
        if not result:
            return jsonify({"error": "Node not found"}), 404
        return jsonify(result[0])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/<label>", methods=["POST"])
def create_node(label):
    data = request.json
    
    # Validate data
    validation = Processor.validate_node_data(label, data)
    if not validation["valid"]:
        return jsonify({"errors": validation["errors"]}), 400
    
    try:
        result = model.create_node(label, data)
        return jsonify(result[0]), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/<label>/<node_id>", methods=["PUT"])
def update_node(label, node_id):
    data = request.json
    
    # Validate data
    validation = Processor.validate_node_data(label, data)
    if not validation["valid"]:
        return jsonify({"errors": validation["errors"]}), 400
    
    try:
        result = model.update_node(label, node_id, data)
        if not result:
            return jsonify({"error": "Node not found"}), 404
        return jsonify(result[0])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/<label>/<node_id>", methods=["DELETE"])
def delete_node(label, node_id):
    try:
        model.delete_node(label, node_id)
        return "", 204
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/relationship", methods=["POST"])
def create_relationship():
    data = request.json
    from_label = data.get("fromLabel")
    from_id = data.get("fromId")
    to_label = data.get("toLabel")
    to_id = data.get("toId")
    rel_type = data.get("type")
    properties = data.get("properties", {})
    
    try:
        result = model.create_relationship(
            from_label, from_id, to_label, to_id, rel_type, properties
        )
        return jsonify(result[0]), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cursor/query", methods=["POST"])
def cursor_query():
    data = request.json
    query = data.get("query")
    params = data.get("params", {})
    cursor_options = data.get("cursorOptions", {})
    
    # Process cursor options
    if "limit" in cursor_options:
        query += " LIMIT $limit"
        params["limit"] = cursor_options["limit"]
    
    if "offset" in cursor_options:
        query += " SKIP $offset"
        params["offset"] = cursor_options["offset"]
    
    try:
        result = model.execute_query(query, params)
        return jsonify({
            "data": result,
            "metadata": {
                "count": len(result)
                # Add other metadata as needed
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Error handler
@app.errorhandler(Exception)
def handle_error(e):
    app.logger.error(f"Server error: {str(e)}")
    return jsonify({
        "error": "Internal server error",
        "message": str(e)
    }), 500

# Cleanup on application exit
@app.teardown_appcontext
def shutdown_session(exception=None):
    model.close()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)