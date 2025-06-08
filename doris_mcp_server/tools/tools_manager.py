# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""
Apache Doris MCP Tools Manager
Responsible for tool registration, management, scheduling and routing, does not contain specific business logic implementation
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List

from mcp.types import Tool

from ..utils.db import DorisConnectionManager
from ..utils.query_executor import DorisQueryExecutor
from ..utils.analysis_tools import TableAnalyzer, PerformanceMonitor
from ..utils.schema_extractor import MetadataExtractor
from ..utils.logger import get_logger

logger = get_logger(__name__)



class DorisToolsManager:
    """Apache Doris Tools Manager"""
    
    def __init__(self, connection_manager: DorisConnectionManager):
        self.connection_manager = connection_manager
        
        # Initialize business logic processors
        self.query_executor = DorisQueryExecutor(connection_manager)
        self.table_analyzer = TableAnalyzer(connection_manager)
        self.performance_monitor = PerformanceMonitor(connection_manager)
        self.metadata_extractor = MetadataExtractor(connection_manager=connection_manager)
        
        logger.info("DorisToolsManager initialized with business logic processors")
    
    async def register_tools_with_mcp(self, mcp):
        """Register all tools to MCP server"""
        logger.info("Starting to register MCP tools")

        # Column statistical analysis tool
        @mcp.tool(
            "column_analysis",
            description="""[Function Description]: Analyze statistical information and data distribution of the specified column.

[Parameter Content]:

- table_name (string) [Required] - Name of the table to analyze

- column_name (string) [Required] - Name of the column to analyze

- analysis_type (string) [Optional] - Type of analysis to perform, default is "basic"
  * "basic": Basic statistics (count, null values, distinct values)
  * "distribution": Data distribution analysis (frequency, percentiles)
  * "detailed": Comprehensive analysis including all above plus patterns and outliers
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Table name"},
                    "column_name": {
                        "type": "string",
                        "description": "Column name to analyze",
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["basic", "distribution", "detailed"],
                        "description": "Analysis type",
                        "default": "basic",
                    },
                },
                "required": ["table_name", "column_name"],
            }
        )
        async def column_analysis_tool(
            table_name: str, 
            column_name: str, 
            analysis_type: str = "basic"
        ) -> str:
            """Column statistical analysis tool"""
            return await self.call_tool("column_analysis", {
                "table_name": table_name,
                "column_name": column_name,
                "analysis_type": analysis_type
            })

        # Database performance monitoring tool
        @mcp.tool(
            "performance_stats[Experimental]",
            description="""[Important]: This tool is experimental and may not be fully functional!
[Function Description]: Get database performance statistics information.

[Parameter Content]:

- metric_type (string) [Optional] - Type of performance metrics to retrieve, default is "queries"
  * "queries": Query performance metrics (execution time, frequency, etc.)
  * "connections": Connection statistics (active connections, connection pool status)
  * "tables": Table-level statistics (size, row count, access patterns)
  * "system": System-level metrics (CPU, memory, disk usage)

- time_range (string) [Optional] - Time range for statistics, default is "1h"
  * "1h": Last 1 hour
  * "6h": Last 6 hours
  * "24h": Last 24 hours
  * "7d": Last 7 days
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric_type": {
                        "type": "string",
                        "enum": ["queries", "connections", "tables", "system"],
                        "description": "Performance metric type",
                        "default": "queries",
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["1h", "6h", "24h", "7d"],
                        "description": "Time range",
                        "default": "1h",
                    },
                },
            }
        )
        async def performance_stats_tool(
            metric_type: str = "queries", 
            time_range: str = "1h"
        ) -> str:
            """Database performance monitoring tool"""
            return await self.call_tool("performance_stats", {
                "metric_type": metric_type,
                "time_range": time_range
            })
        
        # SQL query execution tool (supports catalog federation queries)
        @mcp.tool(
            "exec_query",
            description="""[Function Description]: Execute SQL query and return result command with catalog federation support.

[Parameter Content]:

- sql (string) [Required] - SQL statement to execute. MUST use three-part naming for all table references: 'catalog_name.db_name.table_name'. For internal tables use 'internal.db_name.table_name', for external tables use 'catalog_name.db_name.table_name'

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Reference catalog name for context, defaults to current catalog

- max_rows (integer) [Optional] - Maximum number of rows to return, default 100

- timeout (integer) [Optional] - Query timeout in seconds, default 30
""",
        )
        async def exec_query_tool(
            sql: str,
            db_name: str = None,
            catalog_name: str = None,
            max_rows: int = 100,
            timeout: int = 30,
        ) -> str:
            """Execute SQL query (supports federation queries)"""
            return await self.call_tool("exec_query", {
                "sql": sql,
                "db_name": db_name,
                "catalog_name": catalog_name,
                "max_rows": max_rows,
                "timeout": timeout
            })

        # Get table schema tool
        @mcp.tool(
            "get_table_schema",
            description="""[Function Description]: Get detailed structure information of the specified table (columns, types, comments, etc.).

[Parameter Content]:

- table_name (string) [Required] - Name of the table to query

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
        )
        async def get_table_schema_tool(
            table_name: str, db_name: str = None, catalog_name: str = None
        ) -> str:
            """Get table schema information"""
            return await self.call_tool("get_table_schema", {
                "table_name": table_name,
                "db_name": db_name,
                "catalog_name": catalog_name
            })

        # Get database table list tool
        @mcp.tool(
            "get_db_table_list",
            description="""[Function Description]: Get a list of all table names in the specified database.

[Parameter Content]:

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
        )
        async def get_db_table_list_tool(
            db_name: str = None, catalog_name: str = None
        ) -> str:
            """Get database table list"""
            return await self.call_tool("get_db_table_list", {
                "db_name": db_name,
                "catalog_name": catalog_name
            })

        # Get database list tool
        @mcp.tool(
            "get_db_list",
            description="""[Function Description]: Get a list of all database names on the server.

[Parameter Content]:

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
        )
        async def get_db_list_tool(catalog_name: str = None) -> str:
            """Get database list"""
            return await self.call_tool("get_db_list", {
                "catalog_name": catalog_name
            })

        # Get table comment tool
        @mcp.tool(
            "get_table_comment",
            description="""[Function Description]: Get the comment information for the specified table.

[Parameter Content]:

- table_name (string) [Required] - Name of the table to query

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
        )
        async def get_table_comment_tool(
            table_name: str, db_name: str = None, catalog_name: str = None
        ) -> str:
            """Get table comment"""
            return await self.call_tool("get_table_comment", {
                "table_name": table_name,
                "db_name": db_name,
                "catalog_name": catalog_name
            })

        # Get table column comments tool
        @mcp.tool(
            "get_table_column_comments",
            description="""[Function Description]: Get comment information for all columns in the specified table.

[Parameter Content]:

- table_name (string) [Required] - Name of the table to query

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
        )
        async def get_table_column_comments_tool(
            table_name: str, db_name: str = None, catalog_name: str = None
        ) -> str:
            """Get table column comments"""
            return await self.call_tool("get_table_column_comments", {
                "table_name": table_name,
                "db_name": db_name,
                "catalog_name": catalog_name
            })

        # Get table indexes tool
        @mcp.tool(
            "get_table_indexes",
            description="""[Function Description]: Get index information for the specified table.

[Parameter Content]:

- table_name (string) [Required] - Name of the table to query

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
        )
        async def get_table_indexes_tool(
            table_name: str, db_name: str = None, catalog_name: str = None
        ) -> str:
            """Get table indexes"""
            return await self.call_tool("get_table_indexes", {
                "table_name": table_name,
                "db_name": db_name,
                "catalog_name": catalog_name
            })

        # Get audit logs tool
        @mcp.tool(
            "get_recent_audit_logs",
            description="""[Function Description]: Get audit log records for a recent period.

[Parameter Content]:

- days (integer) [Optional] - Number of recent days of logs to retrieve, default is 7

- limit (integer) [Optional] - Maximum number of records to return, default is 100
""",
        )
        async def get_recent_audit_logs_tool(
            days: int = 7, limit: int = 100
        ) -> str:
            """Get audit logs"""
            return await self.call_tool("get_recent_audit_logs", {
                "days": days,
                "limit": limit
            })

        # Get catalog list tool
        @mcp.tool(
            "get_catalog_list",
            description="""[Function Description]: Get a list of all catalog names on the server.

[Parameter Content]:

- random_string (string) [Required] - Unique identifier for the tool call
""",
        )
        async def get_catalog_list_tool(random_string: str) -> str:
            """Get catalog list"""
            return await self.call_tool("get_catalog_list", {
                "random_string": random_string
            })

        logger.info("Successfully registered 11 tools to MCP server (2 core tools + 9 migrated tools)")

    async def list_tools(self) -> List[Tool]:
        """List all available query tools (for stdio mode)"""
        tools = [
            Tool(
                name="column_analysis[Experimental]",
                description="""[Important]: This tool is experimental and may not be fully functional!
[Function Description]: Analyze statistical information and data distribution of the specified column.

[Parameter Content]:

- table_name (string) [Required] - Name of the table to analyze

- column_name (string) [Required] - Name of the column to analyze

- analysis_type (string) [Optional] - Type of analysis to perform, default is "basic"
  * "basic": Basic statistics (count, null values, distinct values)
  * "distribution": Data distribution analysis (frequency, percentiles)
  * "detailed": Comprehensive analysis including all above plus patterns and outliers
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Table name"},
                        "column_name": {
                            "type": "string",
                            "description": "Column name to analyze",
                        },
                        "analysis_type": {
                            "type": "string",
                            "enum": ["basic", "distribution", "detailed"],
                            "description": "Analysis type",
                            "default": "basic",
                        },
                    },
                    "required": ["table_name", "column_name"],
                },
            ),
            Tool(
                name="performance_stats",
                description="""[Function Description]: Get database performance statistics information.

[Parameter Content]:

- metric_type (string) [Optional] - Type of performance metrics to retrieve, default is "queries"
  * "queries": Query performance metrics (execution time, frequency, etc.)
  * "connections": Connection statistics (active connections, connection pool status)
  * "tables": Table-level statistics (size, row count, access patterns)
  * "system": System-level metrics (CPU, memory, disk usage)

- time_range (string) [Optional] - Time range for statistics, default is "1h"
  * "1h": Last 1 hour
  * "6h": Last 6 hours
  * "24h": Last 24 hours
  * "7d": Last 7 days
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "metric_type": {
                            "type": "string",
                            "enum": ["queries", "connections", "tables", "system"],
                            "description": "Performance metric type",
                            "default": "queries",
                        },
                        "time_range": {
                            "type": "string",
                            "enum": ["1h", "6h", "24h", "7d"],
                            "description": "Time range",
                            "default": "1h",
                        },
                    },
                },
            ),
            Tool(
                name="exec_query",
                description="""[Function Description]: Execute SQL query and return result command with catalog federation support.

[Parameter Content]:

- sql (string) [Required] - SQL statement to execute. MUST use three-part naming for all table references: 'catalog_name.db_name.table_name'. For internal tables use 'internal.db_name.table_name', for external tables use 'catalog_name.db_name.table_name'

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Reference catalog name for context, defaults to current catalog

- max_rows (integer) [Optional] - Maximum number of rows to return, default 100

- timeout (integer) [Optional] - Query timeout in seconds, default 30
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "SQL statement to execute, must use three-part naming"},
                        "db_name": {"type": "string", "description": "Target database name"},
                        "catalog_name": {"type": "string", "description": "Catalog name"},
                        "max_rows": {"type": "integer", "description": "Maximum number of rows to return", "default": 100},
                        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                    },
                    "required": ["sql"],
                },
            ),
            Tool(
                name="get_table_schema",
                description="""[Function Description]: Get detailed structure information of the specified table (columns, types, comments, etc.).

[Parameter Content]:

- table_name (string) [Required] - Name of the table to query

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Table name"},
                        "db_name": {"type": "string", "description": "Database name"},
                        "catalog_name": {"type": "string", "description": "Catalog name"},
                    },
                    "required": ["table_name"],
                },
            ),
            Tool(
                name="get_db_table_list",
                description="""[Function Description]: Get a list of all table names in the specified database.

[Parameter Content]:

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "db_name": {"type": "string", "description": "Database name"},
                        "catalog_name": {"type": "string", "description": "Catalog name"},
                    },
                },
            ),
            Tool(
                name="get_db_list",
                description="""[Function Description]: Get a list of all database names on the server.

[Parameter Content]:

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "catalog_name": {"type": "string", "description": "Catalog name"},
                    },
                },
            ),
            Tool(
                name="get_table_comment",
                description="""[Function Description]: Get the comment information for the specified table.

[Parameter Content]:

- table_name (string) [Required] - Name of the table to query

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Table name"},
                        "db_name": {"type": "string", "description": "Database name"},
                        "catalog_name": {"type": "string", "description": "Catalog name"},
                    },
                    "required": ["table_name"],
                },
            ),
            Tool(
                name="get_table_column_comments",
                description="""[Function Description]: Get comment information for all columns in the specified table.

[Parameter Content]:

- table_name (string) [Required] - Name of the table to query

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Table name"},
                        "db_name": {"type": "string", "description": "Database name"},
                        "catalog_name": {"type": "string", "description": "Catalog name"},
                    },
                    "required": ["table_name"],
                },
            ),
            Tool(
                name="get_table_indexes",
                description="""[Function Description]: Get index information for the specified table.

[Parameter Content]:

- table_name (string) [Required] - Name of the table to query

- db_name (string) [Optional] - Target database name, defaults to the current database

- catalog_name (string) [Optional] - Target catalog name for federation queries, defaults to current catalog
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Table name"},
                        "db_name": {"type": "string", "description": "Database name"},
                        "catalog_name": {"type": "string", "description": "Catalog name"},
                    },
                    "required": ["table_name"],
                },
            ),
            Tool(
                name="get_recent_audit_logs",
                description="""[Function Description]: Get audit log records for a recent period.

[Parameter Content]:

- days (integer) [Optional] - Number of recent days of logs to retrieve, default is 7

- limit (integer) [Optional] - Maximum number of records to return, default is 100
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of recent days", "default": 7},
                        "limit": {"type": "integer", "description": "Maximum number of records", "default": 100},
                    },
                },
            ),
            Tool(
                name="get_catalog_list",
                description="""[Function Description]: Get a list of all catalog names on the server.

[Parameter Content]:

- random_string (string) [Required] - Unique identifier for the tool call
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "random_string": {"type": "string", "description": "Unique identifier"},
                    },
                    "required": ["random_string"],
                },
            ),
        ]
        
        return tools
        
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Call the specified query tool (tool routing and scheduling center)
        """
        try:
            start_time = time.time()
            
            # Tool routing - dispatch requests to corresponding business logic processors
            if name == "column_analysis":
                result = await self._column_analysis_tool(arguments)
            elif name == "performance_stats":
                result = await self._performance_stats_tool(arguments)
            # ===== 9 tool routes migrated from source project =====
            elif name == "exec_query":
                result = await self._exec_query_tool(arguments)
            elif name == "get_table_schema":
                result = await self._get_table_schema_tool(arguments)
            elif name == "get_db_table_list":
                result = await self._get_db_table_list_tool(arguments)
            elif name == "get_db_list":
                result = await self._get_db_list_tool(arguments)
            elif name == "get_table_comment":
                result = await self._get_table_comment_tool(arguments)
            elif name == "get_table_column_comments":
                result = await self._get_table_column_comments_tool(arguments)
            elif name == "get_table_indexes":
                result = await self._get_table_indexes_tool(arguments)
            elif name == "get_recent_audit_logs":
                result = await self._get_recent_audit_logs_tool(arguments)
            elif name == "get_catalog_list":
                result = await self._get_catalog_list_tool(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
            
            execution_time = time.time() - start_time
            
            # Add execution information
            if isinstance(result, dict):
                result["_execution_info"] = {
                    "tool_name": name,
                    "execution_time": round(execution_time, 3),
                    "timestamp": datetime.now().isoformat(),
                }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"Tool call failed {name}: {str(e)}")
            error_result = {
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
                "timestamp": datetime.now().isoformat(),
            }
            return json.dumps(error_result, ensure_ascii=False, indent=2)
    
    # The following are tool routing methods, responsible for calling corresponding business logic processors
    
    async def _column_analysis_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Column statistical analysis tool routing"""
        table_name = arguments.get("table_name")
        column_name = arguments.get("column_name")
        analysis_type = arguments.get("analysis_type", "basic")
        
        # Delegate to table analyzer for processing
        return await self.table_analyzer.analyze_column(
            table_name, column_name, analysis_type
        )
    
    async def _performance_stats_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Database performance statistics tool routing"""
        metric_type = arguments.get("metric_type", "queries")
        time_range = arguments.get("time_range", "1h")
        
        # Delegate to performance monitor for processing
        return await self.performance_monitor.get_performance_stats(
            metric_type, time_range
        )
    
    async def _exec_query_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """SQL query execution tool routing (supports federation queries)"""
        sql = arguments.get("sql")
        db_name = arguments.get("db_name")
        catalog_name = arguments.get("catalog_name")
        max_rows = arguments.get("max_rows", 100)
        timeout = arguments.get("timeout", 30)
        
        # Delegate to metadata extractor for processing
        return await self.metadata_extractor.exec_query_for_mcp(
            sql, db_name, catalog_name, max_rows, timeout
        )
    
    async def _get_table_schema_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get table schema tool routing"""
        table_name = arguments.get("table_name")
        db_name = arguments.get("db_name")
        catalog_name = arguments.get("catalog_name")
        
        # Delegate to metadata extractor for processing
        return await self.metadata_extractor.get_table_schema_for_mcp(
            table_name, db_name, catalog_name
        )
    
    async def _get_db_table_list_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get database table list tool routing"""
        db_name = arguments.get("db_name")
        catalog_name = arguments.get("catalog_name")
        
        # Delegate to metadata extractor for processing
        return await self.metadata_extractor.get_db_table_list_for_mcp(db_name, catalog_name)
    
    async def _get_db_list_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get database list tool routing"""
        catalog_name = arguments.get("catalog_name")
        
        # Delegate to metadata extractor for processing
        return await self.metadata_extractor.get_db_list_for_mcp(catalog_name)
    
    async def _get_table_comment_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get table comment tool routing"""
        table_name = arguments.get("table_name")
        db_name = arguments.get("db_name")
        catalog_name = arguments.get("catalog_name")
        
        # Delegate to metadata extractor for processing
        return await self.metadata_extractor.get_table_comment_for_mcp(
            table_name, db_name, catalog_name
        )
    
    async def _get_table_column_comments_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get table column comments tool routing"""
        table_name = arguments.get("table_name")
        db_name = arguments.get("db_name")
        catalog_name = arguments.get("catalog_name")
        
        # Delegate to metadata extractor for processing
        return await self.metadata_extractor.get_table_column_comments_for_mcp(
            table_name, db_name, catalog_name
        )
    
    async def _get_table_indexes_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get table indexes tool routing"""
        table_name = arguments.get("table_name")
        db_name = arguments.get("db_name")
        catalog_name = arguments.get("catalog_name")
        
        # Delegate to metadata extractor for processing
        return await self.metadata_extractor.get_table_indexes_for_mcp(
            table_name, db_name, catalog_name
        )
    
    async def _get_recent_audit_logs_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get audit logs tool routing"""
        days = arguments.get("days", 7)
        limit = arguments.get("limit", 100)
        
        # Delegate to metadata extractor for processing
        return await self.metadata_extractor.get_recent_audit_logs_for_mcp(days, limit)
    
    async def _get_catalog_list_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get catalog list tool routing"""
        # random_string parameter is required in the source project, but not actually used in business logic
        # Here we ignore it and directly call business logic
        
        # Delegate to metadata extractor for processing
        return await self.metadata_extractor.get_catalog_list_for_mcp() 