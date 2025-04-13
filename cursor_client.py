# cursor_client.py
import requests
from typing import Dict, List, Any, Optional, Generator, Tuple, Callable, TypeVar

T = TypeVar('T')

class Neo4jCursor:
    """A cursor for paginated Neo4j query results"""
    
    def __init__(self, client: 'Neo4jCursorClient', query: str, params: Dict[str, Any] = None, 
                 page_size: int = 20):
        self.client = client
        self.query = query
        self.params = params or {}
        self.page_size = page_size
        self.current_offset = 0
        self.has_more = True
        self.current_page = None
        self.total_count = None
    
    def next(self) -> Dict[str, Any]:
        """Get the next page of results"""
        if not self.has_more:
            return {"value": None, "done": True}
        
        try:
            result = self.client.cursor_query(
                self.query,
                self.params,
                {
                    "limit": self.page_size,
                    "offset": self.current_offset
                }
            )
            
            self.current_page = result["data"]
            self.current_offset += self.page_size
            self.has_more = len(result["data"]) == self.page_size
            
            # Update total count if available
            if "metadata" in result and "count" in result["metadata"]:
                self.total_count = result["metadata"]["count"]
            
            return {"value": self.current_page, "done": False}
        except Exception as e:
            self.has_more = False
            raise e
    
    def reset(self) -> 'Neo4jCursor':
        """Reset the cursor to the beginning"""
        self.current_offset = 0
        self.has_more = True
        self.current_page = None
        return self
    
    def all(self) -> List[Dict[str, Any]]:
        """Get all results at once (use with caution for large datasets)"""
        self.reset()
        all_results = []
        
        while True:
            result = self.next()
            if result["done"]:
                break
            all_results.extend(result["value"])
        
        return all_results
    
    def map(self, callback: Callable[[Dict[str, Any]], T]) -> List[T]:
        """Map function over all results"""
        self.reset()
        results = []
        
        while True:
            result = self.next()
            if result["done"]:
                break
            
            for item in result["value"]:
                results.append(callback(item))
        
        return results
    
    def filter(self, predicate: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
        """Filter results"""
        self.reset()
        results = []
        
        while True:
            result = self.next()
            if result["done"]:
                break
            
            for item in result["value"]:
                if predicate(item):
                    results.append(item)
        
        return results
    
    def __iter__(self) -> Generator[Dict[str, Any], None, None]:
        """Make cursor iterable"""
        self.reset()
        while True:
            result = self.next()
            if result["done"]:
                break
            for item in result["value"]:
                yield item


class Neo4jCursorClient:
    """Client for interacting with Neo4j MCP Server"""
    
    def __init__(self, base_url: str = "http://localhost:5000/api"):
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def set_auth_token(self, token: Optional[str]) -> 'Neo4jCursorClient':
        """Set authentication token if needed"""
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        elif "Authorization" in self.headers:
            del self.headers["Authorization"]
        return self
    
    def request(self, endpoint: str, method: str = "GET", 
                data: Optional[Dict[str, Any]] = None,
                options: Dict[str, Any] = None) -> Any:
        """Helper method for making HTTP requests"""
        options = options or {}
        url = f"{self.base_url}{endpoint}"
        
        request_kwargs = {
            "headers": {**self.headers, **options.get("headers", {})},
        }
        
        if data:
            request_kwargs["json"] = data
        
        response = None
        if method == "GET":
            response = requests.get(url, **request_kwargs)
        elif method == "POST":
            response = requests.post(url, **request_kwargs)
        elif method == "PUT":
            response = requests.put(url, **request_kwargs)
        elif method == "DELETE":
            response = requests.delete(url, **request_kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Check content type and handle response appropriately
        content_type = response.headers.get("content-type", "")
        
        if response.status_code >= 400:
            if "application/json" in content_type:
                error_data = response.json()
                raise Exception(error_data.get("error", "Request failed"))
            else:
                raise Exception(response.text or "Request failed")
        
        if "application/json" in content_type:
            return response.json()
        else:
            return response.text
    
    # Node Operations
    def get_node(self, label: str, node_id: str) -> Dict[str, Any]:
        """Get a node by label and ID"""
        return self.request(f"/{label}/{node_id}")
    
    def create_node(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new node with the specified label"""
        return self.request(f"/{label}", "POST", properties)
    
    def update_node(self, label: str, node_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Update a node"""
        return self.request(f"/{label}/{node_id}", "PUT", properties)
    
    def delete_node(self, label: str, node_id: str) -> None:
        """Delete a node"""
        self.request(f"/{label}/{node_id}", "DELETE")
    
    # Relationship Operations
    def create_relationship(self, from_label: str, from_id: str, 
                           to_label: str, to_id: str, 
                           rel_type: str, 
                           properties: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a relationship between two nodes"""
        data = {
            "fromLabel": from_label,
            "fromId": from_id,
            "toLabel": to_label,
            "toId": to_id,
            "type": rel_type,
            "properties": properties or {}
        }
        return self.request("/relationship", "POST", data)
    
    # Cursor-specific Query Operations
    def cursor_query(self, query: str, params: Dict[str, Any] = None, 
                    cursor_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a query with cursor options"""
        data = {
            "query": query,
            "params": params or {},
            "cursorOptions": cursor_options or {}
        }
        return self.request("/cursor/query", "POST", data)
    
    def cursor(self, query: str, params: Dict[str, Any] = None, 
              page_size: int = 20) -> Neo4jCursor:
        """Returns a cursor for pagination"""
        return Neo4jCursor(self, query, params, page_size)
    
    def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a custom Cypher query"""
        data = {
            "query": query,
            "params": params or {}
        }
        return self.request("/query", "POST", data)


# Example usage:
if __name__ == "__main__":
    # Initialize the client
    client = Neo4jCursorClient("http://localhost:5000/api")
    
    try:
        # Create a node
        person = client.create_node("Person", {
            "id": "123",
            "name": "John Doe",
            "age": 30
        })
        print(f"Created person: {person}")
        
        # Get the node
        retrieved = client.get_node("Person", "123")
        print(f"Retrieved person: {retrieved}")
        
        # Execute a query with cursor pagination
        person_cursor = client.cursor(
            "MATCH (p:Person) WHERE p.age > $min_age RETURN p",
            {"min_age": 25},
            10  # page size
        )
        
        # Process results page by page
        print("Processing people page by page:")
        page_num = 1
        while True:
            result = person_cursor.next()
            if result["done"]:
                break
            
            print(f"Page {page_num} has {len(result['value'])} people")
            for person in result["value"]:
                print(f" - {person['p']['name']}")
            
            page_num += 1
        
        # Or get all results at once
        all_people = person_cursor.all()
        print(f"Found {len(all_people)} people total")
        
        # Or use map to transform results
        names = person_cursor.map(lambda person: person["p"]["name"])
        print(f"Names: {names}")
        
        # Cleanup
        client.delete_node("Person", "123")
        print("Deleted test node")
        
    except Exception as e:
        print(f"Error: {e}")